import AppKit
import WebKit

// A separate 360 x 320 host. It never changes goal data or the production companion.
final class RoomBudgetProbe: NSObject, WKNavigationDelegate {
    private let app = NSApplication.shared
    private var window: NSWindow!
    private var webView: WKWebView!
    private let url: URL
    private let evidenceDirectory: URL
    private let sceneKind: String
    private var openedAt = Date()
    private var readyAt: Date?
    private var didHide = false
    private var didRestore = false
    private var didCaptureRestored = false

    init(url: URL, evidenceDirectory: URL, sceneKind: String) {
        self.url = url
        self.evidenceDirectory = evidenceDirectory
        self.sceneKind = sceneKind
        super.init()
    }

    private func event(_ name: String, _ details: String = "") {
        let now = String(format: "%.3f", Date().timeIntervalSince1970)
        print("event time=\(now) kind=\(name) pid=\(ProcessInfo.processInfo.processIdentifier) visible=\(window?.isVisible ?? false) \(details)")
        fflush(stdout)
    }

    func run() {
        app.setActivationPolicy(.accessory)
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        window = NSWindow(contentRect: NSRect(x: 80, y: 100, width: 360, height: 320),
                          styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "Scene resource probe"
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 360, height: 320), configuration: config)
        webView.navigationDelegate = self
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        openedAt = Date()
        event("launched", "url=\(url.absoluteString) window=360x320")
        webView.load(URLRequest(url: url))
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            self?.tick(timer)
        }
        app.run()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        event("navigation_finished")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        event("navigation_error", "code=\((error as NSError).code)")
    }

    private func snapshot(_ label: String) {
        webView.takeSnapshot(with: nil) { [weak self] image, error in
            guard let self = self else { return }
            guard let image = image, let data = image.tiffRepresentation,
                  let bitmap = NSBitmapImageRep(data: data),
                  let png = bitmap.representation(using: .png, properties: [:]) else {
                self.event("snapshot_error", "label=\(label) code=\((error as NSError?)?.code ?? -1)")
                return
            }
            let path = self.evidenceDirectory.appendingPathComponent("\(label).png")
            do {
                try png.write(to: path)
                self.event("snapshot", "label=\(label) bytes=\(png.count) pixels=\(bitmap.pixelsWide)x\(bitmap.pixelsHigh)")
            } catch {
                self.event("snapshot_write_error", "label=\(label) code=\((error as NSError).code)")
            }
        }
    }

    private func tick(_ timer: Timer) {
        guard let readyAt else {
            if Date().timeIntervalSince(openedAt) > 35 {
                event("ready_timeout")
                timer.invalidate()
                app.terminate(nil)
                return
            }
            let js = sceneKind == "godot"
                ? "JSON.stringify({ready: !!window.__bridgeStatus?.appliedCount, canvas: document.getElementById('room')?.contentWindow?.document.getElementById('canvas')?.width || null})"
                : "JSON.stringify({ready: !!window.__sceneReady, canvas: null})"
            webView.evaluateJavaScript(js) { [weak self] value, error in
                guard let self = self, self.readyAt == nil else { return }
                guard error == nil, let text = value as? String,
                      let data = text.data(using: .utf8),
                      let info = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      info["ready"] as? Bool == true else { return }
                if self.sceneKind == "godot" && info["canvas"] as? Int != 720 { return }
                self.readyAt = Date()
                self.event("ready", "kind=\(self.sceneKind) status=applied")
                self.snapshot("visible-initial")
            }
            return
        }
        let age = Date().timeIntervalSince(readyAt)
        if age >= 30 && !didHide {
            didHide = true
            window.orderOut(nil)
            event("hidden", "since_ready_s=\(String(format: "%.1f", age))")
        }
        if age >= 55 && !didRestore {
            didRestore = true
            window.makeKeyAndOrderFront(nil)
            event("restored", "since_ready_s=\(String(format: "%.1f", age))")
        }
        if age >= 60 && !didCaptureRestored {
            didCaptureRestored = true
            let js = sceneKind == "godot"
                ? "JSON.stringify({state:window.__bridgeStatus || null, hidden:document.hidden, canvas:document.getElementById('room')?.contentWindow?.document.getElementById('canvas')?.width || null})"
                : "JSON.stringify({ready:window.__sceneReady || false, hidden:document.hidden, fallback:document.querySelector('goal-room-scene')?.hasAttribute('data-scene-fallback')})"
            webView.evaluateJavaScript(js) { [weak self] value, error in
                self?.event("restored_state", "js=\(value ?? "nil") error=\(error == nil ? "none" : "eval")")
            }
            snapshot("restored")
        }
        if age >= 75 {
            event("completed")
            timer.invalidate()
            window.close()
            app.terminate(nil)
        }
    }
}

let args = CommandLine.arguments
guard args.count == 4, let url = URL(string: args[1]), ["godot", "pixel"].contains(args[3]) else {
    fputs("usage: WKRoomBudgetProbe URL EVIDENCE_DIRECTORY godot|pixel\n", stderr)
    exit(2)
}
let output = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let probe = RoomBudgetProbe(url: url, evidenceDirectory: output, sceneKind: args[3])
probe.run()

import AppKit
import WebKit

final class SceneBridgeProbe: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    private let app = NSApplication.shared
    private var window: NSWindow!
    private var webView: WKWebView!
    private var tick = 0
    private let url: URL
    private let capturePrefix: String

    init(url: URL, capturePrefix: String) {
        self.url = url
        self.capturePrefix = capturePrefix
        super.init()
    }

    func run() {
        app.setActivationPolicy(.accessory)
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        config.userContentController.add(self, name: "probe")
        config.userContentController.addUserScript(WKUserScript(source: """
            window.addEventListener('error', e => window.webkit.messageHandlers.probe.postMessage('error: ' + e.message));
            window.addEventListener('unhandledrejection', e => window.webkit.messageHandlers.probe.postMessage('rejection: ' + e.reason));
            const oldError = console.error;
            console.error = (...args) => { window.webkit.messageHandlers.probe.postMessage('console-error: ' + args.map(String).join(' ')); oldError.apply(console, args); };
            """, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        window = NSWindow(contentRect: NSRect(x: 80, y: 100, width: 360, height: 320),
                          styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = "Room state bridge probe"
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 360, height: 320), configuration: config)
        webView.navigationDelegate = self
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        print("probe_start url=\(url) window=360x320")
        webView.load(URLRequest(url: url))
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] timer in
            self?.sample(timer: timer)
        }
        app.run()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        print("navigation_finished url=\(webView.url?.absoluteString ?? "nil")")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("navigation_error=\(error)")
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        print("javascript_message=\(message.body)")
    }

    private func capture(_ label: String) {
        webView.takeSnapshot(with: nil) { [weak self] image, error in
            guard let self = self else { return }
            if let image = image, let tiff = image.tiffRepresentation,
               let bitmap = NSBitmapImageRep(data: tiff),
               let png = bitmap.representation(using: .png, properties: [:]) {
                let path = "\(self.capturePrefix)-\(label).png"
                do {
                    try png.write(to: URL(fileURLWithPath: path))
                    print("screenshot_saved=\(path) size=\(png.count)")
                } catch {
                    print("screenshot_error=\(error)")
                }
            } else {
                print("snapshot_error=\(error?.localizedDescription ?? "unknown")")
            }
        }
    }

    private func sample(timer: Timer) {
        tick += 1
        let js = """
        JSON.stringify({bridge:window.__bridgeStatus || null,
          callbackType:typeof document.getElementById('room')?.contentWindow?.careerRoomSetScene,
          canvasSize:document.getElementById('room')?.contentWindow?.document.getElementById('canvas')?.width,
          iframeSize:document.getElementById('room')?.getBoundingClientRect().toJSON()})
        """
        webView.evaluateJavaScript(js) { [weak self] value, error in
            guard let self = self else { return }
            if self.tick % 2 == 0 || self.tick == 1 {
                print("sample_\(self.tick)=\(value ?? "nil") error=\(error?.localizedDescription ?? "none")")
            }
        }
        if tick == 5 { capture("early") }
        if tick == 9 { capture("middle") }
        if tick == 15 { capture("late") }
        if tick >= 18 {
            timer.invalidate()
            window.close()
            app.terminate(nil)
        }
    }
}

let args = CommandLine.arguments
guard args.count == 3, let url = URL(string: args[1]) else {
    fputs("usage: WKSceneBridgeProbe URL SCREENSHOT_PREFIX\n", stderr)
    exit(2)
}
SceneBridgeProbe(url: url, capturePrefix: args[2]).run()

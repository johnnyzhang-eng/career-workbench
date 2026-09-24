import AppKit
import WebKit

final class Probe: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
    private let app = NSApplication.shared
    private var window: NSWindow!
    private var webView: WKWebView!
    private var ticks = 0
    private let url: URL
    private let screenshot: URL
    private let clickStart: Bool

    init(url: URL, screenshot: URL, clickStart: Bool) {
        self.url = url
        self.screenshot = screenshot
        self.clickStart = clickStart
        super.init()
    }

    func run() {
        app.setActivationPolicy(.accessory)
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.userContentController.add(self, name: "probe")
        let script = """
        window.addEventListener('error', e => window.webkit.messageHandlers.probe.postMessage('js-error: ' + e.message));
        window.addEventListener('unhandledrejection', e => window.webkit.messageHandlers.probe.postMessage('rejection: ' + e.reason));
        const oldError = console.error;
        console.error = (...args) => { window.webkit.messageHandlers.probe.postMessage('console-error: ' + args.map(String).join(' ')); oldError.apply(console, args); };
        """
        configuration.userContentController.addUserScript(
            WKUserScript(source: script, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        )
        window = NSWindow(
            contentRect: NSRect(x: 80, y: 100, width: 360, height: 320),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "Godot A · WKWebView Probe"
        webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 360, height: 320), configuration: configuration)
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
        print("navigation_finished")
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        print("navigation_error=\(error)")
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("provisional_navigation_error=\(error)")
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        print("javascript_message=\(message.body)")
    }

    private func sample(timer: Timer) {
        ticks += 1
        if ticks == 7 && clickStart {
            // Start button is x=8..84, y=257..295 in 360x320 top-left canvas CSS coordinates.
            // AppKit window coordinates are bottom-left; send events directly to this probe's WKWebView.
            let point = NSPoint(x: 45, y: 45)
            let timestamp = ProcessInfo.processInfo.systemUptime
            if let down = NSEvent.mouseEvent(with: .leftMouseDown, location: point, modifierFlags: [],
                                             timestamp: timestamp, windowNumber: window.windowNumber,
                                             context: nil, eventNumber: 1, clickCount: 1, pressure: 1.0),
               let up = NSEvent.mouseEvent(with: .leftMouseUp, location: point, modifierFlags: [],
                                           timestamp: timestamp + 0.05, windowNumber: window.windowNumber,
                                           context: nil, eventNumber: 2, clickCount: 1, pressure: 0.0) {
                webView.mouseDown(with: down)
                webView.mouseUp(with: up)
                print("injected_native_click_start x=45 y=45")
            }
        }
        let js = """
        JSON.stringify({
          webgl2: !!document.createElement('canvas').getContext('webgl2'),
          canvasWidth: document.getElementById('canvas')?.width,
          canvasHeight: document.getElementById('canvas')?.height,
          statusPresent: !!document.getElementById('status'),
          title: document.title
        })
        """
        webView.evaluateJavaScript(js) { [weak self] value, error in
            guard let self = self else { return }
            print("sample_\(self.ticks)=\(value ?? "nil") error=\(error?.localizedDescription ?? "none")")
        }
        if ticks == 15 {
            webView.takeSnapshot(with: nil) { [weak self] image, error in
                guard let self = self else { return }
                if let image = image, let data = image.tiffRepresentation,
                   let bitmap = NSBitmapImageRep(data: data),
                   let png = bitmap.representation(using: .png, properties: [:]) {
                    do {
                        try png.write(to: self.screenshot)
                        print("screenshot_saved=\(self.screenshot.path) size=\(png.count)")
                    } catch {
                        print("screenshot_write_error=\(error)")
                    }
                } else {
                    print("snapshot_error=\(error?.localizedDescription ?? "unknown")")
                }
            }
        }
        if ticks >= 20 {
            timer.invalidate()
            window.close()
            app.terminate(nil)
        }
    }
}

let arguments = CommandLine.arguments
guard arguments.count >= 3, arguments.count <= 4, let url = URL(string: arguments[1]) else {
    fputs("usage: WKWebViewProbe URL SCREENSHOT_PATH [--click-start]\n", stderr)
    exit(2)
}
Probe(url: url, screenshot: URL(fileURLWithPath: arguments[2]), clickStart: arguments.last == "--click-start").run()

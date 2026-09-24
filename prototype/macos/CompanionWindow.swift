import AppKit
import WebKit

// This is an experiment for the existing loopback goal companion, not a packaged app.
// All data and task writes still pass through the Python service.

private enum CompanionMode {
    case collapsed
    case compact
    case expanded

    init(path: String) {
        switch path {
        case "/collapsed": self = .collapsed
        case "/compact": self = .compact
        default: self = .expanded
        }
    }

    var size: NSSize {
        switch self {
        case .collapsed: return NSSize(width: 74, height: 74)
        case .compact: return NSSize(width: 360, height: 480)
        case .expanded: return NSSize(width: 1100, height: 760)
        }
    }
}

private final class CompanionPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

private final class ActiveWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override var mouseDownCanMoveWindow: Bool { false }
}

private final class FirstClickButton: NSButton {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override var mouseDownCanMoveWindow: Bool { false }
}

private final class CompanionContentView: NSView {
    override var mouseDownCanMoveWindow: Bool { false }
}

private final class CompanionApp: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private let origin: URL
    private let initialURL: URL
    private var panel: CompanionPanel!
    private var webView: ActiveWebView!
    private var collapsedButton: FirstClickButton!
    private var statusItem: NSStatusItem!
    private var clickThroughItem: NSMenuItem!
    private var mode: CompanionMode = .compact
    private var lastPointerInside = Date()
    private var opacityTimer: Timer?

    init(url: URL) {
        self.initialURL = url
        self.origin = URL(string: "\(url.scheme!)://\(url.host!):\(url.port!)")!
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        webView = ActiveWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.underPageBackgroundColor = .clear
        webView.wantsLayer = true
        webView.layer?.backgroundColor = NSColor.clear.cgColor

        let content = CompanionContentView(frame: NSRect(origin: .zero, size: CompanionMode.compact.size))
        content.wantsLayer = true
        content.layer?.backgroundColor = NSColor.clear.cgColor
        webView.frame = content.bounds
        webView.autoresizingMask = [.width, .height]
        content.addSubview(webView)
        collapsedButton = FirstClickButton(frame: content.bounds)
        collapsedButton.autoresizingMask = [.width, .height]
        collapsedButton.isBordered = false
        collapsedButton.image = NSImage(systemSymbolName: "house.fill", accessibilityDescription: "展开今日房间")
        collapsedButton.imageScaling = .scaleProportionallyDown
        collapsedButton.contentTintColor = .white
        collapsedButton.setAccessibilityLabel("展开今日房间")
        collapsedButton.wantsLayer = true
        collapsedButton.layer?.backgroundColor = NSColor(red: 0.10, green: 0.40, blue: 0.43, alpha: 1).cgColor
        collapsedButton.layer?.cornerRadius = 18
        collapsedButton.target = self
        collapsedButton.action = #selector(showCompanion)
        collapsedButton.isHidden = true
        content.addSubview(collapsedButton)

        panel = CompanionPanel(
            contentRect: NSRect(origin: .zero, size: CompanionMode.compact.size),
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        panel.contentView = content
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.acceptsMouseMovedEvents = true
        panel.makeKeyAndOrderFront(nil)
        resize(for: CompanionMode(path: initialURL.path), animated: false)
        installStatusMenu()
        webView.load(URLRequest(url: initialURL))

        opacityTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            self?.updateOpacity()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        opacityTimer?.invalidate()
    }

    private func installStatusMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "⌂"
        let menu = NSMenu()
        let showItem = NSMenuItem(title: "打开角落小窗", action: #selector(showCompanion), keyEquivalent: "")
        showItem.target = self
        menu.addItem(showItem)
        clickThroughItem = NSMenuItem(title: "鼠标穿透", action: #selector(toggleClickThrough), keyEquivalent: "")
        clickThroughItem.target = self
        menu.addItem(clickThroughItem)
        menu.addItem(.separator())
        let quitItem = NSMenuItem(title: "退出窗口实验", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)
        statusItem.menu = menu
    }

    @objc private func showCompanion() {
        panel.ignoresMouseEvents = false
        clickThroughItem.state = .off
        webView.load(URLRequest(url: compactURL()))
        panel.orderFrontRegardless()
    }

    private func compactURL() -> URL {
        var target = URLComponents(url: origin.appendingPathComponent("compact"), resolvingAgainstBaseURL: false)!
        let current = URLComponents(url: webView.url ?? initialURL, resolvingAgainstBaseURL: false)
        if let goalID = current?.queryItems?.first(where: { $0.name == "goal_id" })?.value,
           !goalID.isEmpty {
            target.queryItems = [URLQueryItem(name: "goal_id", value: goalID)]
        }
        return target.url!
    }

    @objc private func toggleClickThrough() {
        panel.ignoresMouseEvents.toggle()
        clickThroughItem.state = panel.ignoresMouseEvents ? .on : .off
        panel.alphaValue = panel.ignoresMouseEvents ? 0.68 : 1
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }

    private func resize(for newMode: CompanionMode, animated: Bool = true) {
        mode = newMode
        if case .collapsed = newMode {
            webView.isHidden = true
            collapsedButton.isHidden = false
        } else {
            webView.isHidden = false
            collapsedButton.isHidden = true
        }
        let visible = (panel.screen ?? NSScreen.main)?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let width = min(newMode.size.width, visible.width - 24)
        let height = min(newMode.size.height, visible.height - 24)
        let frame = NSRect(
            x: visible.maxX - width - 12,
            y: visible.maxY - height - 12,
            width: width,
            height: height
        )
        panel.setFrame(frame, display: true, animate: animated)
        lastPointerInside = Date()
        updateOpacity()
    }

    private func updateOpacity() {
        guard !panel.ignoresMouseEvents else { return }
        let pointerInside = panel.frame.contains(NSEvent.mouseLocation)
        if pointerInside { lastPointerInside = Date() }
        switch mode {
        case .collapsed: panel.alphaValue = 0.92
        case .expanded: panel.alphaValue = 1
        case .compact:
            panel.alphaValue = pointerInside || Date().timeIntervalSince(lastPointerInside) < 6 ? 1 : 0.82
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url,
              url.scheme == origin.scheme,
              url.host == origin.host,
              url.port == origin.port else {
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let url = webView.url else { return }
        resize(for: CompanionMode(path: url.path))
    }
}

private func companionURL() -> URL? {
    let args = CommandLine.arguments
    let requested = args.count == 1 ? "http://127.0.0.1:8794/compact" :
        (args.count == 3 && args[1] == "--url" ? args[2] : "")
    guard let url = URL(string: requested),
          url.scheme == "http", url.host == "127.0.0.1", url.port != nil,
          ["/", "/compact", "/collapsed"].contains(url.path) else {
        return nil
    }
    return url
}

guard let url = companionURL() else {
    fputs("Usage: CompanionWindow [--url http://127.0.0.1:PORT/compact]\n", stderr)
    exit(2)
}

let app = NSApplication.shared
private let delegate = CompanionApp(url: url)
app.delegate = delegate
app.run()

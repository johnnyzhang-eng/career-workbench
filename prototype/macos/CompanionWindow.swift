import AppKit
import WebKit
import QuartzCore

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

// The still artwork is a replaceable asset. Motion is only triggered by a pointer
// entering or leaving the pet, so the collapsed window has no animation loop.
private final class PetHouseButton: NSButton {
    private var hoverArea: NSTrackingArea?

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override var mouseDownCanMoveWindow: Bool { false }

    override func updateTrackingAreas() {
        if let hoverArea { removeTrackingArea(hoverArea) }
        hoverArea = NSTrackingArea(rect: .zero,
                                 options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                                 owner: self, userInfo: nil)
        if let hoverArea { addTrackingArea(hoverArea) }
        super.updateTrackingAreas()
    }

    override func mouseEntered(with event: NSEvent) { setHoverScale(1.055) }
    override func mouseExited(with event: NSEvent) { setHoverScale(1) }

    private func setHoverScale(_ scale: CGFloat) {
        guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        CATransaction.begin()
        CATransaction.setAnimationDuration(0.18)
        layer?.transform = CATransform3DMakeScale(scale, scale, 1)
        CATransaction.commit()
    }
}

private final class CompanionContentView: NSView {
    override var mouseDownCanMoveWindow: Bool { false }
}

private final class CompanionApp: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private let origin: URL
    private let initialURL: URL
    private var panel: CompanionPanel!
    private var webView: ActiveWebView!
    private var collapsedButton: PetHouseButton!
    private var closeButton: FirstClickButton!
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
        webView.frame = NSRect(x: 0, y: 0, width: content.bounds.width,
                               height: content.bounds.height - 28)
        content.addSubview(webView)
        collapsedButton = PetHouseButton(frame: content.bounds)
        collapsedButton.autoresizingMask = [.width, .height]
        collapsedButton.isBordered = false
        collapsedButton.image = Bundle.main.url(forResource: "pet-room-idle", withExtension: "png")
            .flatMap(NSImage.init(contentsOf:))
            ?? NSImage(systemSymbolName: "house.fill", accessibilityDescription: "展开今日房间")
        collapsedButton.imageScaling = .scaleProportionallyDown
        collapsedButton.setAccessibilityLabel("展开今日房间：房间里有人在书桌前")
        collapsedButton.toolTip = "展开今日房间"
        collapsedButton.wantsLayer = true
        collapsedButton.layer?.backgroundColor = NSColor.clear.cgColor
        collapsedButton.target = self
        collapsedButton.action = #selector(showCompanion)
        collapsedButton.isHidden = true
        content.addSubview(collapsedButton)

        closeButton = FirstClickButton(frame: NSRect(x: 8, y: content.bounds.height - 26,
                                                     width: 22, height: 22))
        closeButton.isBordered = false
        closeButton.image = NSImage(systemSymbolName: "xmark",
                                    accessibilityDescription: "关闭小房间")
        closeButton.imageScaling = .scaleProportionallyDown
        closeButton.contentTintColor = .white
        closeButton.wantsLayer = true
        closeButton.layer?.backgroundColor = NSColor(white: 0.10, alpha: 0.78).cgColor
        closeButton.layer?.cornerRadius = 11
        closeButton.toolTip = "关闭小房间；可从菜单栏 ⌂ 重新打开"
        closeButton.setAccessibilityLabel("关闭小房间")
        closeButton.target = self
        closeButton.action = #selector(hideCompanion)
        content.addSubview(closeButton)

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
        // In the default 74 pt pet state, the browser has no visible work.
        // Defer its first load until the person opens the room.
        if initialURL.path != "/collapsed" {
            webView.load(URLRequest(url: initialURL))
        }

        opacityTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            self?.updateOpacity()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        opacityTimer?.invalidate()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication,
                                       hasVisibleWindows flag: Bool) -> Bool {
        if !flag { showCompanion() }
        return true
    }

    private func installStatusMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "⌂"
        let menu = NSMenu()
        let showItem = NSMenuItem(title: "打开角落小窗", action: #selector(showCompanion), keyEquivalent: "")
        showItem.target = self
        menu.addItem(showItem)
        let hideItem = NSMenuItem(title: "关闭小房间", action: #selector(hideCompanion), keyEquivalent: "w")
        hideItem.target = self
        menu.addItem(hideItem)
        clickThroughItem = NSMenuItem(title: "鼠标穿透", action: #selector(toggleClickThrough), keyEquivalent: "")
        clickThroughItem.target = self
        menu.addItem(clickThroughItem)
        menu.addItem(.separator())
        let quitItem = NSMenuItem(title: "退出应用", action: #selector(quit), keyEquivalent: "q")
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

    @objc private func hideCompanion() {
        panel.orderOut(nil)
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
        let wasCollapsed: Bool
        if case .collapsed = mode { wasCollapsed = true } else { wasCollapsed = false }
        mode = newMode
        let isCollapsed: Bool
        if case .collapsed = newMode {
            isCollapsed = true
            webView.isHidden = true
            collapsedButton.isHidden = false
        } else {
            isCollapsed = false
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
        let showMotion = animated && !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        panel.setFrame(frame, display: true, animate: showMotion)
        if let content = panel.contentView {
            let bounds = content.bounds
            webView.frame = NSRect(x: 0, y: 0, width: bounds.width,
                                   height: bounds.height - (isCollapsed ? 0 : 28))
            collapsedButton.frame = bounds
            let closeSize: CGFloat = isCollapsed ? 17 : 22
            closeButton.frame = NSRect(x: isCollapsed ? bounds.width - closeSize - 2 : 8,
                                       y: bounds.height - closeSize - 4,
                                       width: closeSize, height: closeSize)
            closeButton.layer?.cornerRadius = closeSize / 2
        }
        if wasCollapsed && !isCollapsed && showMotion {
            webView.alphaValue = 0
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.22
                context.timingFunction = CAMediaTimingFunction(name: .easeOut)
                webView.animator().alphaValue = 1
            }
        } else {
            webView.alphaValue = 1
        }
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
    let requested = args.count == 1 ? "http://127.0.0.1:8794/collapsed" :
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

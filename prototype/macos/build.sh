#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
bundle_dir="$repo_dir/private/CareerWorkbenchCompanion.app"
mkdir -p "$bundle_dir/Contents/MacOS"

swiftc -O "$script_dir/CompanionWindow.swift" -o "$bundle_dir/Contents/MacOS/CompanionWindow"
cat > "$bundle_dir/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>org.career-workbench.companion-prototype</string>
  <key>CFBundleName</key><string>Career Workbench Companion</string>
  <key>CFBundleDisplayName</key><string>Career Workbench Companion</string>
  <key>CFBundleExecutable</key><string>CompanionWindow</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>LSUIElement</key><true/>
  <key>NSAppTransportSecurity</key><dict>
    <key>NSAllowsLocalNetworking</key><true/>
  </dict>
</dict></plist>
PLIST

printf '%s\n' "$bundle_dir"

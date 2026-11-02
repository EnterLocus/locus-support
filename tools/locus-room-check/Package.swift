// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "locus-room-check", platforms: [.macOS(.v15)],
    products: [.executable(name: "locus-room-check", targets: ["LocusRoomCheck"])],
    targets: [.executableTarget(name: "LocusRoomCheck")])

// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "VaultAI",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "VaultAI", targets: ["VaultAI"])
    ],
    targets: [
        .executableTarget(
            name: "VaultAI",
            path: "Sources/VaultAI"
        ),
        .testTarget(
            name: "VaultAITests",
            dependencies: ["VaultAI"],
            path: "tests/VaultAITests"
        )
    ]
)

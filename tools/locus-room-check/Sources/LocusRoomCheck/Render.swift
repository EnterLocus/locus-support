// SPDX-License-Identifier: Apache-2.0
import AppKit
import CoreImage
import Foundation
import Metal
import RealityKit
import simd

extension Check {
    @MainActor static func render(_ root: Entity, _ space: [String: Any], _ seats: [Seat], _ directory: URL) async throws -> [String] {
        guard let device = MTLCreateSystemDefaultDevice() else { throw NSError(domain: "Render", code: 1, userInfo: [NSLocalizedDescriptionKey: "Metal GPU unavailable; rendering was not performed."]) }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let renderer = try RealityRenderer()
        renderer.entities.append(root)
        renderer.cameraSettings.colorBackground = .color(CGColor(gray: 0.18, alpha: 1))
        // Neutral constant-gray environment generated from source, no external HDRI.
        let gray = CIImage(color: CIColor(red: 0.5, green: 0.5, blue: 0.5)).cropped(to: CGRect(x: 0, y: 0, width: 128, height: 64))
        let context = CIContext(mtlDevice: device)
        let image = context.createCGImage(gray, from: gray.extent)!
        renderer.lighting.resource = try await EnvironmentResource(equirectangular: image)
        renderer.lighting.intensityExponent = 2
        let sun = DirectionalLight()
        sun.light.intensity = 1500
        sun.look(at: [0, 0, 0], from: [3, 5, 2], relativeTo: nil)
        renderer.entities.append(sun)
        let camera = PerspectiveCamera()
        camera.camera.fieldOfViewInDegrees = 75
        camera.camera.near = 0.01
        camera.camera.far = 200
        renderer.entities.append(camera)
        renderer.activeCamera = camera
        let descriptor = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .bgra8Unorm_srgb, width: 640, height: 360, mipmapped: false)
        descriptor.usage = [.renderTarget, .shaderRead]
        guard let texture = device.makeTexture(descriptor: descriptor) else { throw CocoaError(.fileWriteUnknown) }
        let output = try RealityRenderer.CameraOutput(.singleProjection(colorTexture: texture))
        var files: [String] = []
        var thumbnails: [(String, NSImage)] = []
        func save(_ label: String, _ eye: SIMD3<Float>, _ direction: SIMD3<Float>, up: SIMD3<Float> = [0, 1, 0]) async throws {
            camera.look(at: eye + direction, from: eye, upVector: up, relativeTo: nil)
            // Completion resumes only after the GPU has finished writing the texture.
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                do { try renderer.updateAndRender(deltaTime: 1.0 / 60, cameraOutput: output, onComplete: { _ in continuation.resume() }) }
                catch { continuation.resume(throwing: error) }
            }
            guard let raw = CIImage(mtlTexture: texture, options: [.colorSpace: CGColorSpaceCreateDeviceRGB()]) else { throw CocoaError(.fileWriteUnknown) }
            let flipped = raw.oriented(.downMirrored)
            guard let cg = context.createCGImage(flipped, from: flipped.extent) else { throw CocoaError(.fileWriteUnknown) }
            let bitmap = NSBitmapImageRep(cgImage: cg)
            let url = directory.appendingPathComponent(label + ".png")
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try bitmap.representation(using: .png, properties: [:])!.write(to: url)
            files.append(url.path)
            thumbnails.append((label, NSImage(cgImage: cg, size: NSSize(width: 640, height: 360))))
        }
        for (index, seat) in seats.enumerated() {
            let eye = SIMD3<Float>(seat.eye)
            // Index-based directories keep untrusted author IDs out of filesystem paths.
            for step in 0..<8 {
                let angle = seat.yawRadians + Float(step) * .pi / 4
                try await save("seat-\(index)/yaw-\(step)", eye, [sin(angle), 0, -cos(angle)])
            }
            try await save("seat-\(index)/up", eye, [0, 1, 0], up: [0, 0, 1])
            try await save("seat-\(index)/down", eye, [0, -1, 0], up: [0, 0, -1])
        }
        let b = root.visualBounds(relativeTo: nil)
        let preview = space["previewCamera"] as? [String: Any] ?? [:]
        let yaw = Float(preview["yawDegrees"] as? Double ?? -28) * .pi / 180
        let pitch = min(18, max(-30, Float(preview["pitchDegrees"] as? Double ?? -10))) * .pi / 180
        let zoom = min(1, max(0.72, Float(preview["zoom"] as? Double ?? 0.72)))
        camera.camera.fieldOfViewInDegrees = 45
        let direction = SIMD3<Float>(sin(yaw) * cos(pitch), sin(pitch), -cos(yaw) * cos(pitch))
        let right = simd_normalize(simd_cross(direction, SIMD3<Float>(0, 1, 0)))
        let up = simd_cross(right, direction)
        let tangentY = tan(Float.pi / 8), tangentX = tangentY * 640 / 360
        var distance: Float = 0
        for index in 0..<8 {
            let corner = b.extents / 2 * SIMD3<Float>((index & 1) == 0 ? -1 : 1, (index & 2) == 0 ? -1 : 1, (index & 4) == 0 ? -1 : 1)
            let depth = simd_dot(corner, direction)
            distance = max(distance, max(abs(simd_dot(corner, right)) / tangentX, abs(simd_dot(corner, up)) / tangentY) - depth)
        }
        try await save("preview", b.center - direction * (distance * 1.1 / zoom), direction)
        let columns = 4, tileWidth = 320, tileHeight = 204
        let rows = (thumbnails.count + columns - 1) / columns
        let sheet = NSImage(size: NSSize(width: columns * tileWidth, height: rows * tileHeight))
        sheet.lockFocus()
        NSColor.darkGray.setFill()
        NSRect(origin: .zero, size: sheet.size).fill()
        for (index, pair) in thumbnails.enumerated() {
            let x = index % columns * tileWidth, y = (rows - 1 - index / columns) * tileHeight
            pair.1.draw(in: NSRect(x: x, y: y + 24, width: 320, height: 180))
            (pair.0 + " — scaffolded" as NSString).draw(at: NSPoint(x: x + 4, y: y + 5), withAttributes: [.foregroundColor: NSColor.white, .font: NSFont.systemFont(ofSize: 11)])
        }
        sheet.unlockFocus()
        let bitmap = NSBitmapImageRep(data: sheet.tiffRepresentation!)!
        let url = directory.appendingPathComponent("contact-sheet.png")
        try bitmap.representation(using: .png, properties: [:])!.write(to: url)
        files.append(url.path)
        return files
    }
}

// SPDX-License-Identifier: Apache-2.0
import Foundation
import RealityKit
import AppKit
import simd

struct Finding: Codable { let layer: String; let code: String; let message: String }
struct Seat: Codable { let id: String; let eye: [Float]; let yawRadians: Float }
struct Report: Codable {
    var errors: [Finding] = []
    var warnings: [Finding] = []
    var seats: [Seat] = []
    var macOS = ProcessInfo.processInfo.operatingSystemVersionString
    var layers = ["E", "W"]
    var files: [String] = []
    var renderDurationSeconds: Double?
}
@main struct Check {
    @MainActor static func main() async {
        var report = Report()
        do {
            let args = CommandLine.arguments
            if args.count == 3 && args[1] == "--modelio-budget" {
                let result = inspectModelIOBudget(URL(fileURLWithPath: args[2]))
                let data = try JSONEncoder().encode(result)
                print(String(decoding: data, as: UTF8.self))
                exit(result.error == nil ? 0 : 1)
            }
            guard args.count == 4 || args.count == 5 else { throw CocoaError(.fileReadInvalidFileName) }
            let root = try await Entity(contentsOf: URL(fileURLWithPath: args[1]))
            let space = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[2]))) as! [String: Any]
            let seats = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[3]))) as! [[String: Any]]
            evaluate(root, space, seats, &report)
            if args.count == 5 && !report.seats.isEmpty {
                do {
                    let started = ProcessInfo.processInfo.systemUptime
                    report.files = try await render(root, space, report.seats, URL(fileURLWithPath: args[4]))
                    report.renderDurationSeconds = ProcessInfo.processInfo.systemUptime - started
                    report.layers.append("R")
                } catch {
                    report.errors.append(.init(layer: "R", code: "renderUnavailable", message: error.localizedDescription))
                }
            }
        } catch {
            report.errors.append(.init(layer: "E", code: "modelLoad", message: error.localizedDescription))
        }
        let data = try! JSONEncoder().encode(report)
        print(String(decoding: data, as: UTF8.self))
        exit(report.errors.isEmpty ? 0 : 1)
    }
    @MainActor static func evaluate(_ root: Entity, _ space: [String: Any], _ seats: [[String: Any]], _ report: inout Report) {
        func error(_ code: String, _ message: String) { report.errors.append(.init(layer: "E", code: code, message: message)) }
        func warn(_ code: String, _ message: String) { report.warnings.append(.init(layer: "W", code: code, message: message)) }
        var all: [Entity] = []
        func walk(_ entity: Entity) { all.append(entity); entity.children.forEach(walk) }
        walk(root)
        func entity(_ name: String) -> Entity? {
            let matches = all.filter { $0.name == name }
            guard matches.count == 1 else { error("binding", "Entity '\(name)' must resolve exactly once (found \(matches.count))."); return nil }
            return matches[0]
        }
        let bounds = root.visualBounds(relativeTo: nil)
        let extents = bounds.extents
        if !(0..<3).allSatisfy({ extents[$0].isFinite && extents[$0] > 0.0001 && bounds.min[$0].isFinite && bounds.max[$0].isFinite }) {
            error("invalidModelBounds", "Model visual bounds must be finite and nondegenerate on every axis.")
            return
        }
        if max(extents.x, extents.z) < 1.5 { warn("smallRoom", "Room spans less than 1.5 m horizontally.") }
        if max(extents.x, max(extents.y, extents.z)) > 80 { warn("largeRoom", "Model extends over 80 m; compare geometry with the View sphere on device.") }
        let backdropTokens = ["skybox", "skydome", "sky_dome", "sky-dome", "cyclorama", "backdrop"]
        func hasBackdropName(_ entity: Entity) -> Bool {
            let lower = entity.name.lowercased()
            return backdropTokens.contains { lower.contains($0) }
        }
        for e in all where hasBackdropName(e) && !(e.parent.map(hasBackdropName) ?? false) {
            warn("embeddedBackdrop", "Entity '\(e.name)' looks like an exported skybox or backdrop; keep openings unobstructed in scene.usdz so Locus can display the paired 360° View.")
        }
        let meshBounds = all.filter { $0.components[ModelComponent.self] != nil }.map { ($0.name, $0.visualBounds(relativeTo: nil)) }
        if meshBounds.count >= 3 {
            func median(_ values: [Float]) -> Float { values.sorted()[values.count / 2] }
            let center = SIMD3<Float>(median(meshBounds.map { $0.1.center.x }), median(meshBounds.map { $0.1.center.y }), median(meshBounds.map { $0.1.center.z }))
            let distances = meshBounds.map { simd_length($0.1.center - center) }
            let threshold = max(10, median(distances) * 8)
            for ((name, b), distance) in zip(meshBounds, distances) where distance > threshold {
                warn("boundsPollution", "Mesh '\(name)' center is \(distance) m from the median geometry center (threshold \(threshold) m); check for bounds pollution. Mesh extent: \(b.extents).")
            }
        }
        if let origin = space["seatedOrigin"] as? [String: Any], let q = origin["orientationXYZW"] as? [Double], q.count == 4 {
            let v = SIMD4<Float>(q.map(Float.init))
            let length = simd_length(v)
            if !length.isFinite || length <= 1e-6 { error("seatedOrigin", "seatedOrigin quaternion must be nonzero.") }
            else {
                let up = simd_quatf(vector: v / length).act(SIMD3<Float>(0, 1, 0))
                if abs(up.x) >= 1e-4 || abs(up.z) >= 1e-4 || up.y <= 0.9999 { error("seatedOrigin", "seatedOrigin must remain upright (x/z tilt < 0.0001, up.y > 0.9999).") }
            }
        }
        if seats.isEmpty { error("missingTeleportPoints", "Room must contain at least one seat.") }
        for seat in seats {
            guard let id = seat["id"] as? String, let anchor = seat["anchorXZ"] as? [Double], anchor.count == 2,
                  let floor = seat["sourceFloorOffset"] as? Double, let height = seat["eyeHeight"] as? Double,
                  let yaw = seat["yawRadians"] as? Double else { error("seat", "Seat metadata is incomplete."); continue }
            let eye = SIMD3<Float>(bounds.min.x + Float(anchor[0]) * extents.x, bounds.min.y + Float(floor + height), bounds.min.z + Float(anchor[1]) * extents.z)
            report.seats.append(.init(id: id, eye: [eye.x, eye.y, eye.z], yawRadians: Float(yaw)))
            if anchor.contains(where: { $0 < 0 || $0 > 1 }) || height <= 0 { warn("seatOutsideBounds", "Seat '\(id)' eye is outside XZ bounds or below its floor.") }
            for e in all where e.components[ModelComponent.self] != nil {
                let b = e.visualBounds(relativeTo: nil)
                let delta = simd_max(simd_max(b.min - eye, eye - b.max), .zero)
                if simd_length(delta) < 0.15 { warn("seatClearance", "Seat '\(id)' eye is within 0.15 m of '\(e.name)' bounds (heuristic).") }
            }
        }
        if let adaptation = space["spatialAdaptation"] as? [String: Any] {
            for name in (adaptation["wallEntities"] as? [String] ?? []) + (adaptation["roofEntities"] as? [String] ?? []) { _ = entity(name) }
            let desks = adaptation["deskEntitiesByTeleportID"] as? [String: String] ?? [:]
            let groups = adaptation["deskGroupEntitiesByTeleportID"] as? [String: String] ?? [:]
            for (id, name) in desks.sorted(by: { $0.key < $1.key }) {
                guard let desk = entity(name) else { continue }
                let b = desk.visualBounds(recursive: true, relativeTo: desk)
                let m = desk.transformMatrix(relativeTo: nil)
                let axes = [SIMD3(m.columns.0.x, m.columns.0.y, m.columns.0.z), SIMD3(m.columns.1.x, m.columns.1.y, m.columns.1.z), SIMD3(m.columns.2.x, m.columns.2.y, m.columns.2.z)]
                let lengths = axes.map(simd_length)
                let scores = zip(axes, lengths).map { abs($0.y) / $1 }
                let validAxes = lengths.allSatisfy { $0.isFinite && $0 > 0.0001 } && scores.filter { $0 > 0.9 }.count == 1 && scores.filter { $0 < 0.1 }.count == 2
                if !(0..<3).allSatisfy({ b.extents[$0].isFinite && b.extents[$0] > 0.0001 }) || !validAxes {
                    error("deskBounds", "Desk '\(name)' needs three finite extents > 0.0001 m and an upright basis.")
                }
                if let groupName = groups[id], let group = entity(groupName) {
                    var current: Entity? = desk
                    while let node = current, node !== group { current = node.parent }
                    if current == nil { error("deskGroupSurfaceMismatch", "Desk '\(name)' is outside Hide Desk group '\(groupName)'.") }
                }
            }
        }
        func emissives(_ e: Entity) -> [PhysicallyBasedMaterial] {
            let own = (e.components[ModelComponent.self]?.materials ?? []).compactMap { $0 as? PhysicallyBasedMaterial }.filter { p in
                guard p.emissiveIntensity > 0 else { return false }
                if p.emissiveColor.texture != nil { return true }
                let rgb = p.emissiveColor.color.cgColor.converted(to: CGColorSpaceCreateDeviceRGB(), intent: .defaultIntent, options: nil)?.components ?? []
                return rgb.prefix(3).contains { $0 > 0 }
            }
            return own + e.children.flatMap(emissives)
        }
        func light(_ name: String, opaque: Bool) {
            guard let e = entity(name) else { return }
            let sites = emissives(e)
            if sites.isEmpty { error("entityHasNoPositiveEmissive", "Entity '\(name)' has no authored positive emissive material.") }
            if opaque && !sites.allSatisfy({ if case .opaque = $0.blending { return true }; return false }) {
                error("nonOpaqueEmission", "Entity '\(name)' must use opaque emissive materials.")
            }
        }
        if let lighting = space["lighting"] as? [String: Any] {
            for group in lighting["luminaireGroups"] as? [[String: Any]] ?? [] {
                for name in group["entities"] as? [String] ?? [] { light(name, opaque: false) }
                for name in group["illuminatedEntities"] as? [String] ?? [] { light(name, opaque: true) }
            }
            if let indirect = lighting["bakedIndirect"] as? [String: Any] { for name in indirect["entities"] as? [String] ?? [] { light(name, opaque: true) } }
        }
        for animation in space["ambientAnimations"] as? [[String: Any]] ?? [] {
            guard let name = animation["entityName"] as? String, let clip = animation["animationName"] as? String, let e = entity(name) else { continue }
            if e.components[AnimationLibraryComponent.self]?.animations[clip] == nil && !e.availableAnimations.contains(where: { $0.name == clip }) {
                error("missingAnimation", "Entity '\(name)' has no animation '\(clip)'.")
            }
        }
        warn("deviceAcceptance", "macOS checks do not validate Vision Pro comfort, tracking, Room Portal, real desk alignment, lighting appearance, sound or frame rate.")
    }
}

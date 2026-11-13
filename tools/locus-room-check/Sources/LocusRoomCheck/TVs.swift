// SPDX-License-Identifier: Apache-2.0
import Foundation
import RealityKit
import simd

/// Room TVs (`tvs`, Locus 1.4.9 or later). Locus plays a web page in the
/// bounds of each declared screen, so the screen must be one flat 16:9 quad
/// of its own: not nested under, and not containing, any other entity the
/// Room metadata names.
extension Check {
    /// Every other entity name the Room metadata binds. A TV screen may share
    /// its own name with one of these (for example its own baked-indirect
    /// receiver entry), but must not sit inside or around another.
    static func boundEntityNames(_ space: [String: Any]) -> Set<String> {
        var names = Set<String>()
        func strings(_ value: Any?) -> [String] { value as? [String] ?? [] }
        if let adaptation = space["spatialAdaptation"] as? [String: Any] {
            names.formUnion(strings(adaptation["wallEntities"]))
            names.formUnion(strings(adaptation["roofEntities"]))
            names.formUnion((adaptation["deskEntitiesByTeleportID"] as? [String: String] ?? [:]).values)
            names.formUnion((adaptation["deskGroupEntitiesByTeleportID"] as? [String: String] ?? [:]).values)
        }
        if let rendering = space["rendering"] as? [String: Any] {
            names.formUnion(strings(rendering["softenedReflectionEntities"]))
            names.formUnion(strings(rendering["uiFadeEntities"]))
        }
        if let lighting = space["lighting"] as? [String: Any] {
            for group in lighting["luminaireGroups"] as? [[String: Any]] ?? [] {
                names.formUnion(strings(group["entities"]))
                names.formUnion(strings(group["illuminatedEntities"]))
                let proxies = (group["proxies"] as? [[String: Any]] ?? []) + [group["proxy"] as? [String: Any]].compactMap { $0 }
                names.formUnion(proxies.compactMap { $0["anchorEntity"] as? String })
            }
            names.formUnion(strings((lighting["bakedIndirect"] as? [String: Any])?["entities"]))
        }
        for key in ["ambientAnimations", "videoSurfaces", "tvs"] {
            names.formUnion((space[key] as? [[String: Any]] ?? []).compactMap { $0["entityName"] as? String })
        }
        names.formUnion((space["particleEffects"] as? [[String: Any]] ?? []).compactMap { $0["anchorEntity"] as? String })
        for flow in space["textureFlow"] as? [[String: Any]] ?? [] { names.formUnion(strings(flow["entities"])) }
        return names
    }

    @MainActor static func checkTVs(
        _ space: [String: Any], _ seats: [Seat],
        entity: (String) -> Entity?,
        emissives: (Entity) -> [PhysicallyBasedMaterial],
        error: (String, String) -> Void,
        warn: (String, String) -> Void
    ) {
        let tvs = space["tvs"] as? [[String: Any]] ?? []
        guard !tvs.isEmpty else { return }
        let bound = boundEntityNames(space)
        let baked = Set(((space["lighting"] as? [String: Any])?["bakedIndirect"] as? [String: Any])?["entities"] as? [String] ?? [])
        for tv in tvs {
            guard let name = tv["entityName"] as? String, let screen = entity(name) else { continue }
            var ancestor = screen.parent
            while let node = ancestor {
                if node.name != name && bound.contains(node.name) {
                    error("tvScreenNested", "TV screen '\(name)' is inside '\(node.name)', which the Room also names. Make the screen its own object.")
                }
                ancestor = node.parent
            }
            var meshes: [Entity] = []
            func collect(_ e: Entity) {
                if e !== screen && bound.contains(e.name) && e.name != name {
                    error("tvScreenNested", "TV screen '\(name)' contains '\(e.name)', which the Room also names. Make the screen its own object.")
                }
                if e.components[ModelComponent.self] != nil { meshes.append(e) }
                e.children.forEach(collect)
            }
            collect(screen)
            guard meshes.count == 1, let mesh = meshes.first, let model = mesh.components[ModelComponent.self] else {
                error("tvScreenMesh", "TV screen '\(name)' must contain exactly one mesh (found \(meshes.count)).")
                continue
            }
            let parts = model.mesh.contents.models.flatMap { Array($0.parts) }
            let triangles = parts.reduce(0) { $0 + ($1.triangleIndices?.count ?? 0) / 3 }
            if triangles != 2 {
                error("tvScreenNotQuad", "TV screen '\(name)' must be one flat quad of two triangles (found \(triangles)).")
            }
            if parts.contains(where: { $0.textureCoordinates == nil }) {
                warn("tvScreenUVs", "TV screen '\(name)' has no UVs; give the quad its own 0–1 UVs so its off-state material maps across the whole screen.")
            }
            // Measure in the mesh's own frame, then scale into world meters.
            let local = mesh.visualBounds(relativeTo: mesh)
            let world = mesh.transformMatrix(relativeTo: nil)
            let axes = [world.columns.0, world.columns.1, world.columns.2].map { SIMD3<Float>($0.x, $0.y, $0.z) }
            let size = (0..<3).map { local.extents[$0] * simd_length(axes[$0]) }
            let order = (0..<3).sorted { size[$0] < size[$1] }
            let (thin, height, width) = (size[order[0]], size[order[1]], size[order[2]])
            if !(thin.isFinite && height.isFinite && width.isFinite) || thin > 0.001 || height <= 0 {
                error("tvScreenNotFlat", "TV screen '\(name)' must be a flat rectangle (thickness \(thin) m, size \(width) × \(height) m).")
                continue
            }
            let aspect = width / height
            if abs(aspect - 16.0 / 9.0) > 0.02 * 16.0 / 9.0 {
                warn("tvScreenAspect", "TV screen '\(name)' is \(width) × \(height) m (aspect \(aspect)); Locus fills it with a 16:9 page, so use 16:9.")
            }
            if height < 0.3 {
                warn("tvScreenSmall", "TV screen '\(name)' is only \(height) m tall; a page this small is hard to read from a seat.")
            }
            if !baked.contains(name) && !emissives(screen).isEmpty {
                warn("tvScreenEmissive", "TV screen '\(name)' has an emissive material; its authored material is the off state, so a dark screen should not glow.")
            }
            let normal = simd_normalize(axes[order[0]])
            let center4 = world * SIMD4<Float>(local.center, 1)
            let center = SIMD3<Float>(center4.x, center4.y, center4.z)
            let best = seats.map { seat -> (String, Float) in
                let toEye = SIMD3<Float>(seat.eye[0], seat.eye[1], seat.eye[2]) - center
                let distance = simd_length(toEye)
                guard distance > 0 else { return (seat.id, 90) }
                return (seat.id, acos(min(1, abs(simd_dot(normal, toEye / distance)))) * 180 / .pi)
            }.min { $0.1 < $1.1 }
            if let best, best.1 > 45 {
                warn("tvScreenNoSeat", "No seat faces TV screen '\(name)': the closest to its axis, '\(best.0)', is \(Int(best.1.rounded()))° off. Place the screen to face a seat.")
            }
        }
    }
}

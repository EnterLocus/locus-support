// SPDX-License-Identifier: Apache-2.0
import Foundation
import RealityKit

/// Room interactive states (`interactiveStates`, Locus 1.5.1 or later).
/// Verifies that every `targetEntities` entry holds renderable geometry, every
/// `poses[].entityName` resolves, and every `emissives[].entityName` carries a
/// positive authored emissive material while remaining disjoint from Room
/// lighting (`luminaireGroups` and `bakedIndirect`).
extension Check {
    @MainActor static func checkInteractiveStates(
        _ space: [String: Any],
        entity: (String) -> Entity?,
        emissives: (Entity) -> [PhysicallyBasedMaterial],
        error: (String, String) -> Void
    ) {
        let controls = space["interactiveStates"] as? [[String: Any]] ?? []
        guard !controls.isEmpty else { return }

        var protectedLightingNames = Set<String>()
        if let lighting = space["lighting"] as? [String: Any] {
            for group in lighting["luminaireGroups"] as? [[String: Any]] ?? [] {
                protectedLightingNames.formUnion(group["entities"] as? [String] ?? [])
                protectedLightingNames.formUnion(group["illuminatedEntities"] as? [String] ?? [])
            }
            if let indirect = lighting["bakedIndirect"] as? [String: Any] {
                protectedLightingNames.formUnion(indirect["entities"] as? [String] ?? [])
            }
        }
        let protectedEntities: [(String, Entity)] = protectedLightingNames.sorted().compactMap { name in
            guard let resolved = entity(name) else { return nil }
            return (name, resolved)
        }

        func containsGeometry(_ node: Entity) -> Bool {
            node.components[ModelComponent.self] != nil || node.children.contains(where: containsGeometry)
        }

        func overlaps(_ first: Entity, _ second: Entity) -> Bool {
            var current: Entity? = first
            while let node = current {
                if node === second { return true }
                current = node.parent
            }
            current = second
            while let node = current {
                if node === first { return true }
                current = node.parent
            }
            return false
        }

        var checkedEmissives = Set<String>()
        for control in controls {
            let controlID = control["id"] as? String ?? "?"
            for targetName in control["targetEntities"] as? [String] ?? [] {
                guard let target = entity(targetName) else { continue }
                if !containsGeometry(target) {
                    error("interactiveTargetMesh", "Interactive control '\(controlID)' target '\(targetName)' has no renderable mesh.")
                }
            }
            for state in control["states"] as? [[String: Any]] ?? [] {
                for pose in state["poses"] as? [[String: Any]] ?? [] {
                    if let poseName = pose["entityName"] as? String {
                        _ = entity(poseName)
                    }
                }
                for emissive in state["emissives"] as? [[String: Any]] ?? [] {
                    guard let name = emissive["entityName"] as? String,
                          checkedEmissives.insert(name).inserted,
                          let resolved = entity(name) else { continue }
                    if emissives(resolved).isEmpty {
                        error("entityHasNoPositiveEmissive", "Interactive emissive entity '\(name)' in '\(controlID)' has no authored positive emissive material.")
                    }
                    for (protectedName, protectedEntity) in protectedEntities where overlaps(resolved, protectedEntity) {
                        error("interactiveEmissiveOverlap", "Interactive emissive entity '\(name)' in '\(controlID)' overlaps Room lighting entity '\(protectedName)'.")
                    }
                }
            }
        }
    }
}

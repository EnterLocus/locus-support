// The one public copy of the Room entity-binding contract, resolver and
// model-budget check. Locus runs the same rules on every Room before it
// installs a flat ZIP or a complete Package v2.
//
// Used by:
//   tools/room_bindings.py           (flat and Package v2 validators)
// Keep this file free of a `@main` entry point so every user can link it.

import Foundation
import ModelIO
import RealityKit

/// Resolves an explicit author interface before committing a Room load.
/// Names are exact identities, never material or size classification rules.
@MainActor
enum RoomEntityBindings {
    enum BindingError: LocalizedError, Equatable {
        case missing(String)
        case ambiguous(String)
        case overlapping(String, String)
        case noGeometry(String)

        var errorDescription: String? {
            switch self {
            case .missing(let name): "Room entity '\(name)' was not found."
            case .ambiguous(let name): "Room entity '\(name)' is not uniquely named."
            case .overlapping(let first, let second):
                "Room bindings '\(first)' and '\(second)' overlap in the model hierarchy."
            case .noGeometry(let name): "Room entity '\(name)' has no renderable geometry."
            }
        }
    }

    static func entity(named name: String, in root: Entity) throws -> Entity {
        var matches: [Entity] = []
        func walk(_ entity: Entity) {
            if entity.name == name { matches.append(entity) }
            entity.children.forEach(walk)
        }
        walk(root)
        guard !matches.isEmpty else { throw BindingError.missing(name) }
        guard matches.count == 1 else { throw BindingError.ambiguous(name) }
        return matches[0]
    }

    static func subtrees(named names: [String], in root: Entity) throws -> [Entity] {
        var uniqueNames = Set<String>()
        for name in names where !uniqueNames.insert(name).inserted {
            throw BindingError.ambiguous(name)
        }
        let entities = try names.map { try entity(named: $0, in: root) }
        let ids = Set(entities.map(\.id))
        for entity in entities {
            var parent = entity.parent
            while let ancestor = parent {
                guard !ids.contains(ancestor.id) else {
                    throw BindingError.overlapping(ancestor.name, entity.name)
                }
                parent = ancestor.parent
            }
            guard containsGeometry(entity) else { throw BindingError.noGeometry(entity.name) }
        }
        return entities
    }

    private static func containsGeometry(_ entity: Entity) -> Bool {
        entity.components[ModelComponent.self] != nil
            || entity.children.contains(where: containsGeometry)
    }

    /// Throws if `entity` and `other` are the same node, or one is an
    /// ancestor of the other. Unlike `subtrees(named:in:)` this never
    /// requires geometry; it checks one `illuminatedEntities` reference
    /// against the names it must stay apart from.
    static func requireNoAncestryOverlap(
        _ entity: Entity, named name: String,
        against other: Entity, named otherName: String
    ) throws {
        var current: Entity? = entity
        while let node = current {
            if node === other { throw BindingError.overlapping(otherName, name) }
            current = node.parent
        }
        current = other
        while let node = current {
            if node === entity { throw BindingError.overlapping(name, otherName) }
            current = node.parent
        }
    }
}

/// The subset of the author contract that refers to model entities. Both the
/// public CLI and import preflight decode this from `space.json` (flat ZIP or
/// Package v2), then use the runtime resolver. Full schema and
/// resource-budget validation must precede this check.
struct RoomModelBindingContract: Decodable, Sendable {
    struct Adaptation: Decodable, Sendable {
        let wallEntities: [String]
        let roofEntities: [String]
        let deskEntitiesByTeleportID: [String: String]
        let deskGroupEntitiesByTeleportID: [String: String]?
    }
    struct Rendering: Decodable, Sendable {
        let softenedReflectionEntities: [String]
        let uiFadeEntities: [String]
    }
    struct Lighting: Decodable, Sendable {
        struct Proxy: Decodable, Sendable { let anchorEntity: String }
        struct Group: Decodable, Sendable {
            let entities: [String]
            /// Room v8. Optional so this contract still decodes an
            /// older-format `space.json`.
            let illuminatedEntities: [String]?
            let proxy: Proxy?
            let proxies: [Proxy]?
        }
        struct Indirect: Decodable, Sendable { let entities: [String] }
        let luminaireGroups: [Group]
        let bakedIndirect: Indirect?
    }
    struct Animation: Decodable, Sendable { let entityName: String }
    struct VideoSurface: Decodable, Sendable { let entityName: String }
    /// Package v2 `tvs` (`locus.room.tv.v1`). Each `entityName` is a flat
    /// screen quad: it must resolve to one renderable subtree, none inside
    /// another, like a video surface's.
    struct TV: Decodable, Sendable { let entityName: String }
    /// Only the anchor's position is used, so it resolves by name like a
    /// lighting proxy anchor; a transform-only Xform is enough.
    struct ParticleEffect: Decodable, Sendable { let anchorEntity: String }
    /// Package v2 Room `textureFlow`: every name across every entry resolves
    /// as one renderable subtree, none inside another.
    struct TextureFlow: Decodable, Sendable { let entities: [String] }
    let spatialAdaptation: Adaptation?
    let rendering: Rendering?
    let lighting: Lighting?
    let ambientAnimations: [Animation]?
    let videoSurfaces: [VideoSurface]?
    let particleEffects: [ParticleEffect]?
    let textureFlow: [TextureFlow]?
    let tvs: [TV]?

    var textureFlowNames: [String] { (textureFlow ?? []).flatMap(\.entities) }

    var names: [String] {
        var names: [String] = []
        if let a = spatialAdaptation {
            names += a.wallEntities + a.roofEntities
            names += a.deskEntitiesByTeleportID.sorted { $0.key < $1.key }.map(\.value)
            names += (a.deskGroupEntitiesByTeleportID ?? [:])
                .sorted { $0.key < $1.key }.map(\.value)
        }
        if let r = rendering {
            names += r.softenedReflectionEntities + r.uiFadeEntities
        }
        if let lighting {
            for group in lighting.luminaireGroups {
                names += group.entities
                if let proxy = group.proxy { names.append(proxy.anchorEntity) }
                names += (group.proxies ?? []).map(\.anchorEntity)
            }
            names += lighting.bakedIndirect?.entities ?? []
        }
        names += (ambientAnimations ?? []).map(\.entityName)
        names += (videoSurfaces ?? []).map(\.entityName)
        names += (particleEffects ?? []).map(\.anchorEntity)
        names += textureFlowNames
        names += (tvs ?? []).map(\.entityName)
        return names
    }
}

@MainActor
enum RoomModelBindingValidator {
    /// Locus's import preflight. A Room without authored name references is
    /// not loaded here; its first RealityKit load happens at Preview or entry.
    static func validate(modelURL: URL, contract: RoomModelBindingContract) async throws {
        guard !contract.names.isEmpty else { return }
        let model = try await Entity(contentsOf: modelURL)
        try Task.checkCancellation()
        try validate(model: model, contract: contract)
    }

    /// The same rules against an already loaded model.
    static func validate(model: Entity, contract: RoomModelBindingContract) throws {
        for name in Set(contract.names).sorted() {
            _ = try RoomEntityBindings.entity(named: name, in: model)
        }
        if let rendering = contract.rendering {
            _ = try RoomEntityBindings.subtrees(named: rendering.softenedReflectionEntities, in: model)
            _ = try RoomEntityBindings.subtrees(named: rendering.uiFadeEntities, in: model)
        }
        if let videoSurfaces = contract.videoSurfaces, !videoSurfaces.isEmpty {
            _ = try RoomEntityBindings.subtrees(
                named: videoSurfaces.map(\.entityName), in: model)
        }
        if !contract.textureFlowNames.isEmpty {
            _ = try RoomEntityBindings.subtrees(named: contract.textureFlowNames, in: model)
        }
        if let tvs = contract.tvs, !tvs.isEmpty {
            _ = try RoomEntityBindings.subtrees(named: tvs.map(\.entityName), in: model)
        }
        if let lighting = contract.lighting {
            try validateIlluminatedEntities(lighting, in: model)
        }
    }

    /// Exact-name reuse between `illuminatedEntities` and the other lighting
    /// lists is rejected by schema validation first. Only the live hierarchy
    /// can answer ancestor/descendant containment, which is this check.
    private static func validateIlluminatedEntities(
        _ lighting: RoomModelBindingContract.Lighting, in model: Entity
    ) throws {
        guard lighting.luminaireGroups.contains(where: {
            $0.illuminatedEntities?.isEmpty == false
        }) else { return }
        let entityNames = Set(lighting.luminaireGroups.flatMap(\.entities))
        let bakedNames = Set(lighting.bakedIndirect?.entities ?? [])
        var resolved: [String: Entity] = [:]
        func entity(named name: String) throws -> Entity {
            if let cached = resolved[name] { return cached }
            let value = try RoomEntityBindings.entity(named: name, in: model)
            resolved[name] = value
            return value
        }
        for (index, group) in lighting.luminaireGroups.enumerated() {
            guard let illuminated = group.illuminatedEntities,
                  !illuminated.isEmpty
            else { continue }
            var otherIlluminatedNames = Set<String>()
            for (otherIndex, other) in lighting.luminaireGroups.enumerated()
            where otherIndex != index {
                otherIlluminatedNames.formUnion(other.illuminatedEntities ?? [])
            }
            let protectedNames = entityNames
                .union(bakedNames)
                .union(otherIlluminatedNames)
            for illuminatedName in illuminated {
                let illuminatedEntity = try entity(named: illuminatedName)
                for protectedName in protectedNames {
                    let protectedEntity = try entity(named: protectedName)
                    try RoomEntityBindings.requireNoAncestryOverlap(
                        illuminatedEntity, named: illuminatedName,
                        against: protectedEntity, named: protectedName)
                }
            }
        }
    }
}

/// The flat ZIP's actual-model budget check; author-declared quality numbers
/// must never substitute for inspecting the USD composition and topology.
/// Package v2 counts the flattened stage with `usdcat` instead.
func validateModelBudget(_ url: URL) throws {
    func reject() throws -> Never {
        throw NSError(domain: "Locus", code: 2, userInfo: [NSLocalizedDescriptionKey:
            "scene.usdz exceeds model budget (5,000,000 triangles, 1,024 materials, 100,000 entities; instances are not supported)"])
    }
    let asset = MDLAsset(url: url)
    guard asset.count > 0, asset.originals.objects.isEmpty else { try reject() }
    var pending = (0..<asset.count).map { asset.object(at: $0) }
    var entities = 0
    var triangles = 0
    var materials = Set<ObjectIdentifier>()
    while let object = pending.popLast() {
        guard object.instance == nil else { try reject() }
        entities += 1
        guard entities <= 100_000 else { try reject() }
        pending.append(contentsOf: object.children.objects)
        guard let mesh = object as? MDLMesh, let submeshes = mesh.submeshes else { continue }
        for case let submesh as MDLSubmesh in submeshes {
            let count: Int
            switch submesh.geometryType {
            case .triangles: count = submesh.indexCount / 3
            case .triangleStrips: count = max(0, submesh.indexCount - 2)
            case .quads: count = (submesh.indexCount / 4) * 2
            default: count = submesh.indexCount
            }
            let (sum, overflow) = triangles.addingReportingOverflow(count)
            guard !overflow, sum <= 5_000_000 else { try reject() }
            triangles = sum
            if let material = submesh.material { materials.insert(ObjectIdentifier(material)) }
            guard materials.count <= 1_024 else { try reject() }
        }
    }
}

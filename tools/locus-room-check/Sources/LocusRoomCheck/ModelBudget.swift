// SPDX-License-Identifier: Apache-2.0
import Foundation
import ModelIO

struct ModelIOBudget: Codable {
    var triangles = 0
    var materials = 0
    var entities = 0
    var error: String?
}

func inspectModelIOBudget(_ url: URL) -> ModelIOBudget {
    let asset = MDLAsset(url: url)
    var result = ModelIOBudget()
    guard asset.count > 0 else {
        result.error = "ModelIO could not load the model"
        return result
    }
    guard asset.originals.objects.isEmpty else {
        result.error = "ModelIO reports native originals; App rejects ambiguous instance expansion"
        return result
    }
    var materials = Set<ObjectIdentifier>()
    var pending = (0..<asset.count).map { asset.object(at: $0) }
    while let object = pending.popLast() {
        guard object.instance == nil else {
            result.error = "ModelIO reports a native instance; App rejects ambiguous instance expansion"
            return result
        }
        let (entities, entityOverflow) = result.entities.addingReportingOverflow(1)
        guard !entityOverflow else { result.error = "ModelIO entity count overflow"; return result }
        result.entities = entities
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
            let (triangles, overflow) = result.triangles.addingReportingOverflow(count)
            guard !overflow else { result.error = "ModelIO triangle count overflow"; return result }
            result.triangles = triangles
            if let material = submesh.material { materials.insert(ObjectIdentifier(material)) }
        }
    }
    result.materials = materials.count
    return result
}

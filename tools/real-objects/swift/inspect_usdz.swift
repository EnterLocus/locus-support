// Copyright 2026 EnterLocus.com
// SPDX-License-Identifier: Apache-2.0
// inspect_usdz: metric dimensions, mesh/texture stats and tracking-readiness warnings for a USDZ.
//
//   xcrun swiftc -O swift/inspect_usdz.swift -o .build/inspect_usdz
//   .build/inspect_usdz [--json] [--expect height=95] [--min-height-mm 60] [--max-height-mm 200]
//                       [--min-texture-px 512] model.usdz
//
// Geometry comes from ModelIO (it applies prim transforms but NOT metersPerUnit); units, up axis
// and material facts come from the layer text printed by Xcode's /usr/bin/usdcat.
// Exit status: 0 = inspected (warnings do not change it), 1 = could not load, 2 = usage.

import CoreGraphics
import Foundation
import ImageIO
import ModelIO

struct Options {
    var path = ""
    var json = false
    var minHeightMM = 60.0
    var maxHeightMM = 200.0
    var minTexturePx = 512
    var expectations: [(String, Double)] = []
}

func fail(_ message: String, code: Int32 = 1) -> Never {
    FileHandle.standardError.write(Data(("inspect_usdz: " + message + "\n").utf8))
    exit(code)
}

func parseArguments() -> Options {
    var opts = Options()
    var args = Array(CommandLine.arguments.dropFirst())
    func value(_ flag: String) -> String {
        guard !args.isEmpty else { fail("\(flag) needs a value", code: 2) }
        return args.removeFirst()
    }
    while !args.isEmpty {
        let arg = args.removeFirst()
        switch arg {
        case "--json": opts.json = true
        case "--min-height-mm": opts.minHeightMM = Double(value(arg)) ?? opts.minHeightMM
        case "--max-height-mm": opts.maxHeightMM = Double(value(arg)) ?? opts.maxHeightMM
        case "--min-texture-px": opts.minTexturePx = Int(value(arg)) ?? opts.minTexturePx
        case "--expect":
            let spec = value(arg)
            let parts = spec.split(separator: "=")
            guard parts.count == 2, let mm = Double(parts[1]),
                  ["x", "y", "z", "height"].contains(parts[0].lowercased()) else {
                fail("--expect wants AXIS=MM with AXIS in x|y|z|height, got '\(spec)'", code: 2)
            }
            opts.expectations.append((parts[0].lowercased(), mm))
        case "-h", "--help":
            print("usage: inspect_usdz [--json] [--expect AXIS=MM]... [--min-height-mm N] [--max-height-mm N] [--min-texture-px N] model.usdz")
            exit(0)
        default:
            if arg.hasPrefix("--") { fail("unknown option \(arg)", code: 2) }
            if !opts.path.isEmpty { fail("only one input file is supported", code: 2) }
            opts.path = arg
        }
    }
    if opts.path.isEmpty { fail("missing input USDZ path", code: 2) }
    return opts
}

func run(_ executable: String, _ arguments: [String]) -> (status: Int32, out: String, err: String) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: executable)
    process.arguments = arguments
    let outPipe = Pipe(), errPipe = Pipe()
    process.standardOutput = outPipe
    process.standardError = errPipe
    do { try process.run() } catch { return (127, "", "\(error)") }
    // Drain stdout before waiting so a large layer cannot fill the pipe and deadlock.
    let out = outPipe.fileHandleForReading.readDataToEndOfFile()
    let err = errPipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    return (process.terminationStatus, String(decoding: out, as: UTF8.self), String(decoding: err, as: UTF8.self))
}

struct Warning {
    let code: String
    let severity: String   // "error" blocks `train` without --force; "warn" is advisory.
    let message: String
    var dict: [String: Any] { ["code": code, "severity": severity, "message": message] }
}

struct TextureInfo {
    let path: String
    var present = false
    var width = 0, height = 0
    var bytes = 0
    var hasAlphaChannel = false
    var minAlpha = 1.0
    var lumaMean = 0.0
    var maxChannelStd = 0.0
    var role = "color"   // "color" feeds diffuse/base colour; "data" is normal/roughness/etc.
    var dict: [String: Any] {
        var d: [String: Any] = ["path": path, "present": present, "role": role]
        if present {
            d["width"] = width; d["height"] = height; d["bytes"] = bytes
            d["hasAlphaChannel"] = hasAlphaChannel; d["minAlpha"] = minAlpha
            d["lumaMean"] = lumaMean; d["maxChannelStdDev"] = maxChannelStd
        }
        return d
    }
}

func analyzeImage(at url: URL, into info: inout TextureInfo) {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return }
    info.present = true
    info.width = image.width
    info.height = image.height
    info.bytes = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
    switch image.alphaInfo {
    case .none, .noneSkipFirst, .noneSkipLast: info.hasAlphaChannel = false
    default: info.hasAlphaChannel = true
    }
    // Downscale to at most 256 px per side: enough to judge variance, cheap for 8K scans.
    let scale = min(1.0, 256.0 / Double(max(image.width, image.height)))
    let w = max(1, Int(Double(image.width) * scale)), h = max(1, Int(Double(image.height) * scale))
    var pixels = [UInt8](repeating: 0, count: w * h * 4)
    guard let context = CGContext(data: &pixels, width: w, height: h, bitsPerComponent: 8,
                                  bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return }
    context.interpolationQuality = .low
    context.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
    var sum = [Double](repeating: 0, count: 3), sumSq = [Double](repeating: 0, count: 3)
    var minAlpha = 255.0
    let count = Double(w * h)
    for i in 0..<(w * h) {
        let a = Double(pixels[i * 4 + 3])
        minAlpha = min(minAlpha, a)
        // Un-premultiply so a transparent edge does not read as dark colour.
        for c in 0..<3 {
            var v = Double(pixels[i * 4 + c])
            if a > 0 { v = min(255, v * 255 / a) }
            v /= 255
            sum[c] += v; sumSq[c] += v * v
        }
    }
    var maxStd = 0.0
    for c in 0..<3 {
        let mean = sum[c] / count
        maxStd = max(maxStd, (max(0, sumSq[c] / count - mean * mean)).squareRoot())
    }
    info.maxChannelStd = maxStd
    info.lumaMean = (0.2126 * sum[0] + 0.7152 * sum[1] + 0.0722 * sum[2]) / count
    info.minAlpha = minAlpha / 255
}

func firstMatch(_ pattern: String, in text: String) -> String? {
    guard let regex = try? NSRegularExpression(pattern: pattern),
          let m = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
          m.numberOfRanges > 1, let r = Range(m.range(at: 1), in: text) else { return nil }
    return String(text[r])
}

func allMatches(_ pattern: String, in text: String) -> [String] {
    guard let regex = try? NSRegularExpression(pattern: pattern) else { return [] }
    return regex.matches(in: text, range: NSRange(text.startIndex..., in: text)).compactMap { m in
        m.numberOfRanges > 1 ? Range(m.range(at: 1), in: text).map { String(text[$0]) } : nil
    }
}

func fmt(_ v: Double, _ digits: Int = 1) -> String { String(format: "%.\(digits)f", v) }

// MARK: - main

let opts = parseArguments()
let inputURL = URL(fileURLWithPath: opts.path)
guard FileManager.default.fileExists(atPath: inputURL.path) else { fail("no such file: \(opts.path)") }

// Unpack the archive so textures can be located and decoded.
let ext = inputURL.pathExtension.lowercased()
let workDir = FileManager.default.temporaryDirectory.appendingPathComponent("inspect_usdz-\(UUID().uuidString)")
defer { try? FileManager.default.removeItem(at: workDir) }
var packageFiles: [String: URL] = [:]
if ext == "usdz" {
    try? FileManager.default.createDirectory(at: workDir, withIntermediateDirectories: true)
    let unzip = run("/usr/bin/unzip", ["-o", "-q", inputURL.path, "-d", workDir.path])
    if unzip.status != 0 { fail("cannot unpack \(opts.path): \(unzip.err)") }
    if let walker = FileManager.default.enumerator(at: workDir, includingPropertiesForKeys: [.isRegularFileKey]) {
        for case let url as URL in walker where (try? url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true {
            let rel = String(url.path.dropFirst(workDir.path.count + 1))
            packageFiles[rel] = url
        }
    }
} else {
    packageFiles[inputURL.lastPathComponent] = inputURL
}

// Layer text: units, up axis and material facts.
let cat = run("/usr/bin/usdcat", [inputURL.path])
let layerText = cat.status == 0 ? cat.out : ""
let header: String = {
    guard let r = layerText.range(of: "\ndef ") ?? layerText.range(of: "\nover ") else { return layerText }
    return String(layerText[..<r.lowerBound])
}()
let authoredMPU = firstMatch(#"metersPerUnit\s*=\s*([0-9.eE+\-]+)"#, in: header).flatMap(Double.init)
let metersPerUnit = authoredMPU ?? 0.01   // USD fallback when unauthored
let headerUp = firstMatch(#"upAxis\s*=\s*"([XYZxyz])""#, in: header)?.uppercased()

// Geometry via ModelIO.
let asset = MDLAsset(url: inputURL)
let meshes = asset.childObjects(of: MDLMesh.self).compactMap { $0 as? MDLMesh }
var vertexCount = 0, triangleCount = 0, submeshCount = 0
var otherPrimitiveSubmeshes = 0
for mesh in meshes {
    vertexCount += mesh.vertexCount
    for case let sub as MDLSubmesh in (mesh.submeshes ?? []) {
        submeshCount += 1
        switch sub.geometryType {
        case .triangles: triangleCount += sub.indexCount / 3
        case .quads: triangleCount += sub.indexCount / 4 * 2
        case .variableTopology:
            // Polygon counts live in topology.faceTopology.
            if let topo = sub.topology {
                guard let counts = topo.faceTopology else { continue }
                let n = topo.faceCount
                let ptr = counts.map().bytes.assumingMemoryBound(to: Int32.self)
                for i in 0..<n { triangleCount += max(0, Int(ptr[i]) - 2) }
            }
        default: otherPrimitiveSubmeshes += 1
        }
    }
}

var warnings: [Warning] = []
let box = asset.boundingBox
let rawExtent = [Double(box.maxBounds.x - box.minBounds.x),
                 Double(box.maxBounds.y - box.minBounds.y),
                 Double(box.maxBounds.z - box.minBounds.z)]
let hasGeometry = !meshes.isEmpty && vertexCount > 0 && rawExtent.allSatisfy { $0.isFinite }
if !hasGeometry {
    warnings.append(Warning(code: "no-geometry", severity: "error",
                            message: "ModelIO found no mesh geometry in this file; it cannot be tracked."))
}

let upVector = asset.upAxis
var upIndex = 1
if upVector.z > 0.5 { upIndex = 2 } else if upVector.x > 0.5 { upIndex = 0 }
if let h = headerUp { upIndex = ["X": 0, "Y": 1, "Z": 2][h] ?? upIndex }
let upName = ["X", "Y", "Z"][upIndex]
let extentMM = rawExtent.map { $0 * metersPerUnit * 1000 }
let heightMM = hasGeometry ? extentMM[upIndex] : 0
let originMM = [Double(box.minBounds.x), Double(box.minBounds.y), Double(box.minBounds.z)].map { $0 * metersPerUnit * 1000 }

if authoredMPU == nil {
    warnings.append(Warning(code: "units-not-authored", severity: "warn",
        message: "metersPerUnit is not authored; USD falls back to 0.01 (centimetres) and dimensions here assume that. Apple tools often assume metres, so check the size against calipers."))
}
if hasGeometry && (heightMM < opts.minHeightMM || heightMM > opts.maxHeightMM) {
    warnings.append(Warning(code: "implausible-scale", severity: "error",
        message: "Height along \(upName) is \(fmt(heightMM)) mm, outside the plausible mug range \(fmt(opts.minHeightMM, 0))–\(fmt(opts.maxHeightMM, 0)) mm. Check units/scale before training (rescale_usdz can fix a wrong size)."))
}
if hasGeometry && upName != "Y" {
    warnings.append(Warning(code: "up-axis", severity: "warn",
        message: "upAxis is \(upName); ARKit reference objects expect a Y-up model. Re-export with Y up if tracking looks rotated."))
}

// Rigid / single-model facts.
let topLevelPrims = allMatches(#"(?m)^(?:def|over)\s+\w*\s*"([^"]+)""#, in: layerText)
let skeletonCount = allMatches(#"(?m)^\s*def\s+(SkelRoot|Skeleton|SkelAnimation)\b"#, in: layerText).count
let animated = layerText.contains("timeSamples") || layerText.contains("startTimeCode")
var rigidNotes: [String] = []
if skeletonCount > 0 { rigidNotes.append("contains skeleton/skinning prims") }
if animated { rigidNotes.append("has time-sampled (animated) attributes") }
if topLevelPrims.count > 1 { rigidNotes.append("\(topLevelPrims.count) top-level prims (\(topLevelPrims.joined(separator: ", "))); expected one root") }
let isRigid = rigidNotes.isEmpty
if !isRigid {
    warnings.append(Warning(code: "not-rigid", severity: "warn",
        message: "Not a single rigid model: " + rigidNotes.joined(separator: "; ") + ". Object tracking needs one static rigid object."))
}

// Textures.
let textureRefs = Array(Set(allMatches(#"@([^@]+\.(?:png|jpg|jpeg|exr|tif|tiff|heic|bmp|webp))@"#, in: layerText))).sorted()
var textures: [TextureInfo] = []
// Which textures feed diffuse/base colour? Follow `inputs:diffuseColor.connect` to the shader that
// reads the file; without connection info fall back to file-name hints (norm/rough/ao/...).
var currentShader = ""
var filesByShader: [String: Set<String>] = [:]
for line in layerText.split(separator: "\n", omittingEmptySubsequences: true) {
    let text = String(line)
    if let name = firstMatch(#"^\s*def\s+Shader\s+"([^"]+)""#, in: text) { currentShader = name }
    if let file = firstMatch(#"inputs:file\s*=\s*@([^@]+)@"#, in: text) { filesByShader[currentShader, default: []].insert(file) }
}
let diffuseShaders = Set(allMatches(#"inputs:(?:diffuseColor|baseColor)\.connect\s*=\s*<([^>]+)>"#, in: layerText).map {
    String($0.split(separator: "/").last ?? "").components(separatedBy: ".outputs").first ?? ""
})
let colourPaths = Set(diffuseShaders.flatMap { filesByShader[$0] ?? [] })
let dataNameHint = try! NSRegularExpression(pattern: "norm|rough|metal|occl|(^|[_/\\-])ao[_0-9.]|bump|height|disp|opacity|mask", options: .caseInsensitive)
func textureRole(_ ref: String) -> String {
    if !colourPaths.isEmpty { return colourPaths.contains(ref) ? "color" : "data" }
    return dataNameHint.firstMatch(in: ref, range: NSRange(ref.startIndex..., in: ref)) != nil ? "data" : "color"
}
for ref in textureRefs {
    var info = TextureInfo(path: ref)
    info.role = textureRole(ref)
    let normalized = ref.hasPrefix("./") ? String(ref.dropFirst(2)) : ref
    if let url = packageFiles[normalized] ?? packageFiles.first(where: { $0.key.hasSuffix("/" + normalized) })?.value {
        analyzeImage(at: url, into: &info)
    }
    textures.append(info)
}
let materialCount = allMatches(#"(?m)^\s*def\s+Material\s+"([^"]+)""#, in: layerText).count
let missing = textures.filter { !$0.present }
let present = textures.filter { $0.present }
if !missing.isEmpty {
    warnings.append(Warning(code: "missing-texture", severity: "warn",
        message: "Textures referenced but absent or unreadable: " + missing.map { $0.path }.joined(separator: ", ")))
}
if textureRefs.isEmpty && hasGeometry {
    warnings.append(Warning(code: "no-texture", severity: "warn",
        message: "No textures referenced (\(materialCount) material(s)). Geometry alone gives the tracker little to latch onto unless the shape is distinctive."))
}
for t in present where t.role == "color" && max(t.width, t.height) < opts.minTexturePx {
    warnings.append(Warning(code: "low-texture-resolution", severity: "warn",
        message: "Texture \(t.path) is only \(t.width)×\(t.height) px (< \(opts.minTexturePx) px on its long side)."))
}
for t in present where t.role == "color" && t.maxChannelStd < 0.03 {
    warnings.append(Warning(code: "uniform-texture", severity: "warn",
        message: "Texture \(t.path) is nearly one colour (max channel std-dev \(fmt(t.maxChannelStd, 3))). Symmetric or plain objects can't be tracked reliably; a printed or textured surface helps."))
}

// Transparency.
let opacityConnected = layerText.range(of: #"inputs:opacity\.connect"#, options: .regularExpression) != nil
let opacityValues = allMatches(#"inputs:opacity\s*=\s*([0-9.eE+\-]+)"#, in: layerText).compactMap(Double.init)
let opacityLessThanOne = opacityValues.contains { $0 < 0.999 }
let thresholdAuthored = layerText.contains("inputs:opacityThreshold")
let alphaTextureUsed = opacityConnected && present.contains { $0.hasAlphaChannel && $0.minAlpha < 0.999 }
if opacityLessThanOne || thresholdAuthored || alphaTextureUsed {
    var why: [String] = []
    if opacityLessThanOne { why.append("opacity < 1") }
    if thresholdAuthored { why.append("opacityThreshold (cutout)") }
    if alphaTextureUsed { why.append("alpha-textured opacity") }
    warnings.append(Warning(code: "transparency", severity: "warn",
        message: "Transparent material (" + why.joined(separator: ", ") + "). Translucent or cut-out surfaces track poorly; bake an opaque model."))
}

// Expectations vs calipers.
var comparisons: [[String: Any]] = []
for (axis, expected) in opts.expectations {
    let actual: Double
    switch axis {
    case "x": actual = extentMM[0]
    case "y": actual = extentMM[1]
    case "z": actual = extentMM[2]
    default: actual = heightMM
    }
    let deviation = expected > 0 ? (actual - expected) / expected * 100 : 0
    comparisons.append(["axis": axis, "expectedMM": expected, "actualMM": actual,
                        "deviationPercent": deviation, "scaleToMatch": actual > 0 ? expected / actual : 0,
                        "within1Percent": abs(deviation) <= 1.0])
}

let report: [String: Any] = [
    "file": inputURL.path,
    "units": ["metersPerUnit": metersPerUnit, "authored": authoredMPU != nil, "upAxis": upName],
    "dimensionsMM": ["x": extentMM[0], "y": extentMM[1], "z": extentMM[2], "height": heightMM,
                     "upAxis": upName, "boundsMinMM": originMM],
    "mesh": ["meshCount": meshes.count, "submeshCount": submeshCount, "vertices": vertexCount,
             "triangles": triangleCount],
    "materials": ["count": materialCount],
    "textures": textures.map { $0.dict },
    "rigid": ["singleRigidModel": isRigid, "notes": rigidNotes, "topLevelPrims": topLevelPrims],
    "comparisons": comparisons,
    "warnings": warnings.map { $0.dict },
    "plausibleRangeMM": ["min": opts.minHeightMM, "max": opts.maxHeightMM],
]

if opts.json {
    let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} else {
    print("File:        \(inputURL.path)")
    print("Units:       metersPerUnit=\(metersPerUnit)\(authoredMPU == nil ? " (not authored, USD fallback)" : ""), up axis \(upName)")
    if hasGeometry {
        print("Dimensions:  X \(fmt(extentMM[0])) mm × Y \(fmt(extentMM[1])) mm × Z \(fmt(extentMM[2])) mm   (height along \(upName): \(fmt(heightMM)) mm)")
    } else {
        print("Dimensions:  unavailable (no geometry)")
    }
    print("Mesh:        \(meshes.count) mesh(es), \(submeshCount) submesh(es), \(vertexCount) vertices, \(triangleCount) triangles")
    print("Materials:   \(materialCount)")
    if textures.isEmpty {
        print("Textures:    none")
    } else {
        print("Textures:")
        for t in textures {
            if t.present {
                print("  - \(t.path) [\(t.role)]: \(t.width)×\(t.height) px, \(t.bytes) bytes, colour std-dev \(fmt(t.maxChannelStd, 3)), mean luma \(fmt(t.lumaMean, 2))\(t.hasAlphaChannel ? ", alpha (min \(fmt(t.minAlpha, 2)))" : "")")
            } else {
                print("  - \(t.path): MISSING")
            }
        }
    }
    print("Rigid:       \(isRigid ? "yes, single rigid model" : "NO — " + rigidNotes.joined(separator: "; "))")
    for c in comparisons {
        let dev = c["deviationPercent"] as? Double ?? 0
        let scale = c["scaleToMatch"] as? Double ?? 0
        print("Expected:    \(c["axis"] as! String) \(fmt(c["expectedMM"] as! Double)) mm vs \(fmt(c["actualMM"] as! Double)) mm (\(dev >= 0 ? "+" : "")\(fmt(dev, 2))%); scale factor to match \(fmt(scale, 4))\(abs(dev) <= 1 ? " — within 1%, no rescale needed" : " — rescale_usdz recommended")")
    }
    if warnings.isEmpty {
        print("Warnings:    none")
    } else {
        print("Warnings:")
        for w in warnings { print("  [\(w.severity)] \(w.code): \(w.message)") }
    }
}

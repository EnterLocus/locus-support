// Copyright 2026 EnterLocus.com
// SPDX-License-Identifier: Apache-2.0
// reconstruct: rebuild a USDZ from a folder of Object Capture images with RealityKit's
// PhotogrammetrySession (macOS).
//
//   xcrun swiftc -O swift/reconstruct.swift -o .build/reconstruct
//   .build/reconstruct --input <images> --output model.usdz [--detail full] [--ordering sequential]
//                      [--feature-sensitivity normal] [--checkpoint <dir>] [--no-object-masking] [--dry-run]
//
// Input is the folder of iPhone Object Capture shots (HEIC with embedded depth; JPEG/PNG/TIFF work
// without depth). Exit status: 0 = model written, 1 = failed/cancelled, 2 = usage or bad input.

import Foundation
import RealityKit

func fail(_ message: String, code: Int32 = 1) -> Never {
    FileHandle.standardError.write(Data(("reconstruct: " + message + "\n").utf8))
    exit(code)
}

struct Options {
    var input = ""
    var output = ""
    var detail = "full"
    var ordering = "unordered"
    var sensitivity = "normal"
    var checkpoint: String?
    var masking = true
    var dryRun = false
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
        case "--input", "-i": opts.input = value(arg)
        case "--output", "-o": opts.output = value(arg)
        case "--detail": opts.detail = value(arg).lowercased()
        case "--ordering": opts.ordering = value(arg).lowercased()
        case "--feature-sensitivity": opts.sensitivity = value(arg).lowercased()
        case "--checkpoint": opts.checkpoint = value(arg)
        case "--no-object-masking": opts.masking = false
        case "--dry-run": opts.dryRun = true
        case "-h", "--help":
            print("""
            usage: reconstruct --input <image folder> --output <model.usdz>
                               [--detail reduced|medium|full|raw]        (default full)
                               [--ordering sequential|unordered]         (default unordered)
                               [--feature-sensitivity normal|high]       (default normal)
                               [--checkpoint <dir>]  resume-able working directory
                               [--no-object-masking] [--dry-run]
            """)
            exit(0)
        default: fail("unknown option \(arg)", code: 2)
        }
    }
    if opts.input.isEmpty { fail("missing --input", code: 2) }
    if opts.output.isEmpty { fail("missing --output", code: 2) }
    if !["reduced", "medium", "full", "raw"].contains(opts.detail) { fail("--detail must be reduced|medium|full|raw", code: 2) }
    if !["sequential", "unordered"].contains(opts.ordering) { fail("--ordering must be sequential|unordered", code: 2) }
    if !["normal", "high"].contains(opts.sensitivity) { fail("--feature-sensitivity must be normal|high", code: 2) }
    if !opts.output.lowercased().hasSuffix(".usdz") { fail("--output must end in .usdz", code: 2) }
    return opts
}

let imageExtensions: Set<String> = ["heic", "heif", "jpg", "jpeg", "png", "tif", "tiff", "dng"]

func imageFiles(in folder: URL) throws -> [URL] {
    let items = try FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.isRegularFileKey],
                                                            options: [.skipsHiddenFiles])
    return items.filter { imageExtensions.contains($0.pathExtension.lowercased()) }
}

let opts = parseArguments()
let inputURL = URL(fileURLWithPath: opts.input, isDirectory: true)
var isDirectory: ObjCBool = false
guard FileManager.default.fileExists(atPath: inputURL.path, isDirectory: &isDirectory) else {
    fail("input folder does not exist: \(opts.input)", code: 2)
}
guard isDirectory.boolValue else { fail("input must be a folder of images, not a file: \(opts.input)", code: 2) }
let images: [URL]
do { images = try imageFiles(in: inputURL) } catch { fail("cannot read \(opts.input): \(error.localizedDescription)", code: 2) }
if images.isEmpty {
    fail("no images (\(imageExtensions.sorted().joined(separator: ", "))) found in \(opts.input)", code: 2)
}
if images.count < 10 {
    FileHandle.standardError.write(Data("reconstruct: warning: only \(images.count) images; Object Capture usually needs 30+ overlapping shots\n".utf8))
}
let heicCount = images.filter { ["heic", "heif"].contains($0.pathExtension.lowercased()) }.count
let outputURL = URL(fileURLWithPath: opts.output)

print("Input:       \(inputURL.path) (\(images.count) images, \(heicCount) HEIC)")
print("Output:      \(outputURL.path)")
print("Detail:      \(opts.detail), ordering \(opts.ordering), feature sensitivity \(opts.sensitivity), object masking \(opts.masking ? "on" : "off")")
if let c = opts.checkpoint { print("Checkpoint:  \(c)") }
if opts.dryRun {
    print("Dry run: input looks usable; no reconstruction started.")
    exit(0)
}

guard PhotogrammetrySession.isSupported else {
    fail("PhotogrammetrySession is not supported on this Mac (needs Apple silicon or a supported GPU)")
}
try? FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)

var configuration = PhotogrammetrySession.Configuration()
configuration.sampleOrdering = opts.ordering == "sequential" ? .sequential : .unordered
configuration.featureSensitivity = opts.sensitivity == "high" ? .high : .normal
configuration.isObjectMaskingEnabled = opts.masking
if let c = opts.checkpoint {
    let url = URL(fileURLWithPath: c, isDirectory: true)
    try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    configuration.checkpointDirectory = url
}

let detail: PhotogrammetrySession.Request.Detail
switch opts.detail {
case "reduced": detail = .reduced
case "medium": detail = .medium
case "raw": detail = .raw
default: detail = .full
}

let session: PhotogrammetrySession
do {
    session = try PhotogrammetrySession(input: inputURL, configuration: configuration)
} catch {
    fail("cannot start a session on \(opts.input): \(error.localizedDescription)")
}

// Ctrl-C cancels cleanly; with --checkpoint the next run resumes from the saved stages.
signal(SIGINT, SIG_IGN)
let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interrupt.setEventHandler {
    print("\nInterrupted, cancelling session...")
    session.cancel()
}
interrupt.resume()

func inspectBinary() -> String? {
    let fm = FileManager.default
    if let env = ProcessInfo.processInfo.environment["ROS_INSPECT"], fm.isExecutableFile(atPath: env) { return env }
    let exeDir = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath().deletingLastPathComponent()
    for candidate in [exeDir.appendingPathComponent("inspect_usdz"),
                      exeDir.deletingLastPathComponent().appendingPathComponent(".build/inspect_usdz")]
    where fm.isExecutableFile(atPath: candidate.path) { return candidate.path }
    return nil
}

func reportOutput() {
    guard let inspect = inspectBinary() else {
        print("(inspect_usdz not found next to this binary; run it on \(outputURL.path) to check the size)")
        return
    }
    print("\nInspecting \(outputURL.lastPathComponent):")
    let process = Process()
    process.executableURL = URL(fileURLWithPath: inspect)
    process.arguments = [outputURL.path]
    try? process.run()
    process.waitUntilExit()
}

let started = Date()
var lastPercent = -1
Task {
    do {
        for try await output in session.outputs {
            switch output {
            case .requestProgress(_, let fraction):
                let percent = Int(fraction * 100)
                if percent != lastPercent {
                    lastPercent = percent
                    print(String(format: "[%5.0fs] %3d%%", Date().timeIntervalSince(started), percent))
                    fflush(stdout)
                }
            case .requestProgressInfo(_, let info):
                var parts: [String] = []
                if let stage = info.processingStage { parts.append("stage \(stage)") }
                if let eta = info.estimatedRemainingTime { parts.append(String(format: "~%.0f min left", eta / 60)) }
                if !parts.isEmpty { print("         " + parts.joined(separator: ", ")); fflush(stdout) }
            case .requestComplete(_, .modelFile(let url)):
                print("Model written: \(url.path)")
            case .requestComplete:
                break
            case .requestError(_, let error):
                fail("reconstruction failed: \(error.localizedDescription)")
            case .invalidSample(let id, let reason):
                print("warning: sample \(id) rejected: \(reason)")
            case .skippedSample(let id):
                print("warning: sample \(id) skipped")
            case .automaticDownsampling:
                print("warning: input exceeded GPU limits, automatically downsampling")
            case .stitchingIncomplete:
                print("warning: stitching incomplete; the images may not overlap enough for one model")
            case .inputComplete:
                print("Input accepted, processing...")
            case .processingCancelled:
                fail("cancelled")
            case .processingComplete:
                print(String(format: "Done in %.0f s.", Date().timeIntervalSince(started)))
                if FileManager.default.fileExists(atPath: outputURL.path) {
                    reportOutput()
                    exit(0)
                }
                fail("processing finished but no model file was written")
            @unknown default:
                break
            }
        }
    } catch {
        fail("session error: \(error.localizedDescription)")
    }
}

do {
    try session.process(requests: [.modelFile(url: outputURL, detail: detail)])
} catch {
    fail("cannot start processing: \(error.localizedDescription)")
}
dispatchMain()

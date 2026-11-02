// Command-line entry point for the shared Room binding check
// (RoomBindings.swift). tools/room_bindings.py compiles both files with
// `xcrun --sdk macosx swiftc -parse-as-library` and runs the result.

import Foundation

@main
struct ValidateRoomBindings {
    static func main() async {
        do {
            var arguments = Array(CommandLine.arguments.dropFirst())
            let checkModelBudget = arguments.first == "--model-budget"
            if checkModelBudget { arguments.removeFirst() }
            guard arguments.count == 2 else {
                throw NSError(domain: "Locus", code: 2, userInfo: [NSLocalizedDescriptionKey:
                    "Usage: validate-room-bindings [--model-budget] scene.usdz space.json"])
            }
            let modelURL = URL(fileURLWithPath: arguments[0])
            if checkModelBudget { try validateModelBudget(modelURL) }
            let contract = try JSONDecoder().decode(RoomModelBindingContract.self,
                from: Data(contentsOf: URL(fileURLWithPath: arguments[1])))
            try await RoomModelBindingValidator.validate(modelURL: modelURL, contract: contract)
        } catch {
            FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
            exit(2)
        }
    }
}

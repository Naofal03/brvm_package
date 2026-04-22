import Foundation
import PDFKit

enum SplitFailure: Error {
    case usage
    case cannotOpen(String)
    case cannotWrite(String)
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("usage: split_pdf_pages.swift <input-pdf> <output-dir>\n", stderr)
    throw SplitFailure.usage
}

let inputPath = args[1]
let outputDir = URL(fileURLWithPath: args[2], isDirectory: true)
try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)

guard let document = PDFDocument(url: URL(fileURLWithPath: inputPath)) else {
    throw SplitFailure.cannotOpen(inputPath)
}

for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else {
        continue
    }
    let newDocument = PDFDocument()
    if let copiedPage = page.copy() as? PDFPage {
        newDocument.insert(copiedPage, at: 0)
    } else {
        newDocument.insert(page, at: 0)
    }
    let outputPath = outputDir.appendingPathComponent(String(format: "page-%03d.pdf", index + 1))
    guard newDocument.write(to: outputPath) else {
        throw SplitFailure.cannotWrite(outputPath.path)
    }
    print(outputPath.path)
}

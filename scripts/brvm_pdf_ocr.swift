import Foundation
import Vision
import AppKit
import PDFKit

struct OCRToken: Codable {
    let text: String
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let confidence: Double
}

struct OCRPage: Codable {
    let page_number: Int
    let width: Double
    let height: Double
    let tokens: [OCRToken]
}

struct OCRDocument: Codable {
    let source: String
    let page_count: Int
    let pages: [OCRPage]
}

enum OCRFailure: Error {
    case missingPath
    case cannotOpenPDF(String)
    case cannotOpenImage(String)
    case cannotRenderPage(Int)
}

func render(page: PDFPage, scale: CGFloat = 2.5) throws -> (CGImage, CGSize) {
    let bounds = page.bounds(for: .mediaBox)
    let width = max(Int(bounds.width * scale), 1)
    let height = max(Int(bounds.height * scale), 1)

    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else {
        throw OCRFailure.cannotRenderPage(0)
    }

    rep.size = NSSize(width: bounds.width, height: bounds.height)
    NSGraphicsContext.saveGraphicsState()
    guard let context = NSGraphicsContext(bitmapImageRep: rep) else {
        throw OCRFailure.cannotRenderPage(0)
    }

    NSGraphicsContext.current = context
    NSColor.white.set()
    NSBezierPath(rect: NSRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height))).fill()

    let cgContext = context.cgContext
    cgContext.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: cgContext)
    NSGraphicsContext.restoreGraphicsState()

    guard let cgImage = rep.cgImage else {
        throw OCRFailure.cannotRenderPage(0)
    }

    return (cgImage, CGSize(width: bounds.width, height: bounds.height))
}

func recognize(pageNumber: Int, cgImage: CGImage, pageSize: CGSize) throws -> OCRPage {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["fr-FR", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    let tokens = observations.compactMap { observation -> OCRToken? in
        guard let candidate = observation.topCandidates(1).first else {
            return nil
        }
        let box = observation.boundingBox
        return OCRToken(
            text: candidate.string,
            x: Double(box.minX),
            y: Double(box.minY),
            width: Double(box.width),
            height: Double(box.height),
            confidence: Double(candidate.confidence)
        )
    }

    return OCRPage(
        page_number: pageNumber,
        width: Double(pageSize.width),
        height: Double(pageSize.height),
        tokens: tokens
    )
}

func recognizeImage(path: String) throws -> OCRDocument {
    let url = URL(fileURLWithPath: path)
    guard let image = NSImage(contentsOf: url) else {
        throw OCRFailure.cannotOpenImage(path)
    }
    var rect = NSRect(origin: .zero, size: image.size)
    guard let cgImage = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
        throw OCRFailure.cannotOpenImage(path)
    }
    let page = try recognize(pageNumber: 1, cgImage: cgImage, pageSize: image.size)
    return OCRDocument(source: path, page_count: 1, pages: [page])
}

func recognizePDF(path: String) throws -> OCRDocument {
    let url = URL(fileURLWithPath: path)
    guard let document = PDFDocument(url: url) else {
        throw OCRFailure.cannotOpenPDF(path)
    }

    var pages: [OCRPage] = []
    for index in 0..<document.pageCount {
        guard let page = document.page(at: index) else {
            continue
        }
        let (image, size) = try render(page: page)
        let recognizedPage = try recognize(pageNumber: index + 1, cgImage: image, pageSize: size)
        pages.append(recognizedPage)
    }

    return OCRDocument(source: path, page_count: document.pageCount, pages: pages)
}

let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
    fputs("usage: brvm_pdf_ocr.swift <path>\n", stderr)
    throw OCRFailure.missingPath
}

let path = arguments[1]
let lowerPath = path.lowercased()
let payload: OCRDocument
if lowerPath.hasSuffix(".pdf") {
    payload = try recognizePDF(path: path)
} else {
    payload = try recognizeImage(path: path)
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
let output = try encoder.encode(payload)
FileHandle.standardOutput.write(output)

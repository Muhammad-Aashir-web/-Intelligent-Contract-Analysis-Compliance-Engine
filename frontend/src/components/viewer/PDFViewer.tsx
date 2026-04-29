import { useState } from "react"
import { X } from "lucide-react"
import { Document, Page, pdfjs } from "react-pdf"

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

type PDFViewerProps = {
	fileUrl: string
	fileName?: string
	onClear?: () => void
}

type DocumentLoadSuccess = {
	numPages: number
}

function PDFViewer({ fileUrl, fileName, onClear }: PDFViewerProps) {
	const [numPages, setNumPages] = useState<number | null>(null)
	const [pageNumber, setPageNumber] = useState<number>(1)
	const [scale, setScale] = useState<number>(1.0)

	const onDocumentLoadSuccess = ({ numPages: loadedNumPages }: DocumentLoadSuccess) => {
		setNumPages(loadedNumPages)
		setPageNumber(1)
	}

	const onDocumentLoadError = (error: unknown) => {
		console.log(error)
	}

	const handlePreviousPage = () => {
		setPageNumber((currentPage) => Math.max(currentPage - 1, 1))
	}

	const handleNextPage = () => {
		setPageNumber((currentPage) => Math.min(currentPage + 1, numPages ?? currentPage))
	}

	const handleZoomOut = () => {
		setScale((currentScale) => Math.max(currentScale - 0.2, 0.6))
	}

	const handleZoomIn = () => {
		setScale((currentScale) => Math.min(currentScale + 0.2, 2.0))
	}

	return (
		<div className="flex flex-col bg-white rounded-lg border border-gray-200 overflow-hidden">
			<div className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
				<div className="text-sm text-gray-600">{fileName ?? ""}</div>
				{onClear ? (
					<button
						type="button"
						onClick={onClear}
						className="text-gray-400 hover:text-red-500"
						aria-label="Clear PDF"
					>
						<X size={18} />
					</button>
				) : null}
			</div>

			<div className="flex items-center justify-center p-4 min-h-[400px]">
				<Document file={fileUrl} onLoadSuccess={onDocumentLoadSuccess} onLoadError={onDocumentLoadError}>
					<Page
						pageNumber={pageNumber}
						scale={scale}
						width={600}
						renderTextLayer={false}
						renderAnnotationLayer={false}
					/>
				</Document>
			</div>

			<div className="flex justify-center items-center gap-4 p-3 bg-white border-t border-gray-200">
				<button
					type="button"
					className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-700"
					disabled={pageNumber === 1}
					onClick={handlePreviousPage}
				>
					Previous
				</button>
				<span className="text-sm text-gray-700">
					Page {pageNumber} of {numPages ?? 0}
				</span>
				<button
					type="button"
					className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-700"
					disabled={numPages === null || pageNumber === numPages}
					onClick={handleNextPage}
				>
					Next
				</button>
				<button
					type="button"
					className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-700"
					disabled={scale <= 0.6}
					onClick={handleZoomOut}
				>
					-
				</button>
				<span className="text-sm text-gray-700">{Math.round(scale * 100)}%</span>
				<button
					type="button"
					className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-40 hover:bg-blue-700"
					disabled={scale >= 2.0}
					onClick={handleZoomIn}
				>
					+
				</button>
			</div>
		</div>
	)
}

export default PDFViewer
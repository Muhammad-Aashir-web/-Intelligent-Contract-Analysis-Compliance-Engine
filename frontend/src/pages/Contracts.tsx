import { useEffect, useState } from "react"
import { Loader2, X } from "lucide-react"

import ClauseList from "../components/clauses/ClauseList"
import Layout from "../components/layout/Layout"
import FileUpload from "../components/viewer/FileUpload"
import PDFViewer from "../components/viewer/PDFViewer"
import useContract from "../hooks/useContract"

function Contracts() {
	const [fileUrl, setFileUrl] = useState<string | null>(null)
	const [fileName, setFileName] = useState<string | null>(null)
	const [showViewer, setShowViewer] = useState<boolean>(false)

	const {
		uploadAndAnalyze,
		isLoading,
		isAnalyzing,
		analysisResult,
		error,
		clearError,
	} = useContract()

	useEffect(() => {
		return () => {
			if (fileUrl) {
				URL.revokeObjectURL(fileUrl)
			}
		}
	}, [fileUrl])

	const handleFileSelect = (file: File) => {
		if (fileUrl) {
			URL.revokeObjectURL(fileUrl)
		}

		const nextUrl = URL.createObjectURL(file)
		setFileUrl(nextUrl)
		setFileName(file.name)
		setShowViewer(true)
		void uploadAndAnalyze(file)
	}

	const handleClear = () => {
		if (fileUrl) {
			URL.revokeObjectURL(fileUrl)
		}

		setFileUrl(null)
		setFileName(null)
		setShowViewer(false)
		clearError()
	}

	return (
		<Layout title="Contracts">
			<div className="space-y-6">
				<div className="flex items-center justify-between">
					<h2 className="text-2xl font-semibold text-gray-900">Contracts</h2>
				</div>

				{isAnalyzing ? (
					<div className="flex items-center gap-3 rounded-lg bg-yellow-100 border border-yellow-200 px-4 py-3 text-yellow-800">
						<Loader2 className="h-5 w-5 animate-spin" />
						<span className="text-sm font-medium">Analyzing contract with AI agents...</span>
					</div>
				) : null}

				{error ? (
					<div className="flex items-center justify-between gap-3 rounded-lg bg-red-100 border border-red-200 px-4 py-3 text-red-700">
						<span className="text-sm font-medium">{error}</span>
						<button
							type="button"
							onClick={clearError}
							className="text-red-500 hover:text-red-700"
							aria-label="Clear error"
						>
							<X className="h-4 w-4" />
						</button>
					</div>
				) : null}

				{showViewer && fileUrl ? (
					<div className="grid grid-cols-2 gap-6">
						<div className="w-1/2">
							<FileUpload onFileSelect={handleFileSelect} isUploading={isLoading || isAnalyzing} />
						</div>
						<div className="w-1/2">
							<PDFViewer fileUrl={fileUrl} fileName={fileName ?? undefined} onClear={handleClear} />
						</div>
					</div>
				) : (
					<div className="flex justify-center">
						<div className="w-full max-w-3xl">
							<FileUpload onFileSelect={handleFileSelect} isUploading={isLoading || isAnalyzing} />
						</div>
					</div>
				)}

				{analysisResult ? (
					<div className="space-y-6">
						<div className="bg-white rounded-xl shadow-sm p-6">
							<h3 className="font-semibold text-gray-800 mb-4">Overall Risk Score: {analysisResult.overallRiskScore}</h3>
						</div>

						<div className="bg-white rounded-xl shadow-sm p-6">
							<h3 className="font-semibold text-gray-800 mb-4">Clauses</h3>
							<ClauseList clauses={analysisResult.clauses} />
						</div>

						<div className="bg-white rounded-xl shadow-sm p-6">
							<h3 className="font-semibold text-gray-800 mb-4">Summary</h3>
							<p className="text-sm text-gray-700 leading-relaxed">{analysisResult.summary}</p>
						</div>
					</div>
				) : null}
			</div>
		</Layout>
	)
}

export default Contracts
import { useEffect, useRef, useState, type ChangeEvent } from "react"

import Layout from "../components/layout/Layout"
import FileUpload from "../components/viewer/FileUpload"
import PDFViewer from "../components/viewer/PDFViewer"

function Contracts() {
	const [selectedFile, setSelectedFile] = useState<File | null>(null)
	const [fileUrl, setFileUrl] = useState<string | null>(null)
	const [isUploading, setIsUploading] = useState<boolean>(false)
	const [showViewer, setShowViewer] = useState<boolean>(false)
	const hiddenFileInputRef = useRef<HTMLInputElement | null>(null)

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

		setSelectedFile(file)
		setIsUploading(false)
		const nextUrl = URL.createObjectURL(file)
		setFileUrl(nextUrl)
		setShowViewer(true)
	}

	const handleClear = () => {
		if (fileUrl) {
			URL.revokeObjectURL(fileUrl)
		}

		setSelectedFile(null)
		setFileUrl(null)
		setShowViewer(false)
	}

	const handleHiddenFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0]
		if (file) {
			handleFileSelect(file)
		}
		event.target.value = ""
	}

	const triggerFileInputClick = () => {
		hiddenFileInputRef.current?.click()
	}

	return (
		<Layout title="Contracts">
			<div className="space-y-6">
				<div className="flex items-center justify-between">
					<h2 className="text-2xl font-semibold text-gray-900">Contracts</h2>
					<button
						type="button"
						className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
						onClick={triggerFileInputClick}
					>
						Upload Contract
					</button>
				</div>

				<input
					ref={hiddenFileInputRef}
					type="file"
					className="hidden"
					accept=".pdf,.doc,.docx"
					onChange={handleHiddenFileInputChange}
				/>

				{showViewer && fileUrl ? (
					<div className="grid grid-cols-2 gap-6">
						<div className="flex items-start justify-center">
							<div className="w-full">
								<FileUpload onFileSelect={handleFileSelect} isUploading={isUploading} />
							</div>
						</div>
						<div className="h-96 overflow-auto">
							<PDFViewer fileUrl={fileUrl} fileName={selectedFile?.name} onClear={handleClear} />
						</div>
					</div>
				) : (
					<div className="flex justify-center">
						<div className="w-full max-w-3xl">
							<FileUpload onFileSelect={handleFileSelect} isUploading={isUploading} />
						</div>
					</div>
				)}
			</div>
		</Layout>
	)
}

export default Contracts

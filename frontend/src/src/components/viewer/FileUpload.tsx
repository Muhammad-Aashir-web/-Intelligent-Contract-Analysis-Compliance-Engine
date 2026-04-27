import { useRef, useState, type ChangeEvent, type DragEvent } from "react"
import { Upload } from "lucide-react"

type FileUploadProps = {
	onFileSelect: (file: File) => void
	isUploading: boolean
	acceptedTypes?: string
}

function FileUpload({
	onFileSelect,
	isUploading,
	acceptedTypes = ".pdf,.doc,.docx",
}: FileUploadProps) {
	const [isDragOver, setIsDragOver] = useState<boolean>(false)
	const fileInputRef = useRef<HTMLInputElement | null>(null)

	const handleFile = (file: File | undefined) => {
		if (!file) {
			return
		}

		onFileSelect(file)
	}

	const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
		event.preventDefault()
		event.stopPropagation()
		setIsDragOver(true)
	}

	const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
		event.preventDefault()
		event.stopPropagation()
		setIsDragOver(false)
	}

	const handleDrop = (event: DragEvent<HTMLDivElement>) => {
		event.preventDefault()
		event.stopPropagation()
		setIsDragOver(false)
		handleFile(event.dataTransfer.files[0])
	}

	const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
		handleFile(event.target.files?.[0])
	}

	const triggerFilePicker = () => {
		fileInputRef.current?.click()
	}

	if (isUploading) {
		return (
			<div className="flex items-center justify-center gap-3 rounded-xl border-2 border-dashed border-blue-400 bg-blue-50 p-12 text-center">
				<div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
				<span className="text-lg font-medium text-gray-700">Uploading...</span>
			</div>
		)
	}

	const uploadZoneClassName = isDragOver
		? "border-blue-400 bg-blue-50"
		: "border-gray-300 bg-gray-50"

	return (
		<div
			className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer ${uploadZoneClassName}`}
			onClick={triggerFilePicker}
			onDragOver={handleDragOver}
			onDragLeave={handleDragLeave}
			onDrop={handleDrop}
			role="button"
			tabIndex={0}
			onKeyDown={(event) => {
				if (event.key === "Enter" || event.key === " ") {
					event.preventDefault()
					triggerFilePicker()
				}
			}}
		>
			<input
				ref={fileInputRef}
				type="file"
				className="hidden"
				accept={acceptedTypes}
				onChange={handleInputChange}
			/>

			<div className="flex flex-col items-center justify-center gap-3">
				<Upload size={48} className="text-blue-400" />
				<p className="text-lg font-medium text-gray-700">Drag and drop your contract here</p>
				<p className="text-sm text-gray-500">or click to browse files</p>
				<p className="text-xs text-gray-400">Supported: PDF, DOC, DOCX (max 50MB)</p>
			</div>
		</div>
	)
}

export default FileUpload

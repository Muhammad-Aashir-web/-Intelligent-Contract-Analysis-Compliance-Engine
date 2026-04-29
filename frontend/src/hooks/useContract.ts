import { useState } from "react"

import contractService from "../services/contractService"
import type { AnalysisResult, Contract } from "../types/contract"

type UseContractReturn = {
	contracts: Contract[]
	currentContract: Contract | null
	analysisResult: AnalysisResult | null
	isLoading: boolean
	isAnalyzing: boolean
	error: string | null
	uploadProgress: number
	fetchContracts: () => Promise<void>
	uploadAndAnalyze: (file: File) => Promise<void>
	clearError: () => void
}

function useContract(): UseContractReturn {
	const [contracts, setContracts] = useState<Contract[]>([])
	const [currentContract, setCurrentContract] = useState<Contract | null>(null)
	const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
	const [isLoading, setIsLoading] = useState<boolean>(false)
	const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false)
	const [error, setError] = useState<string | null>(null)
	const [uploadProgress, setUploadProgress] = useState<number>(0)

	const clearError = () => {
		setError(null)
	}

	const fetchContracts = async () => {
		try {
			setIsLoading(true)
			setError(null)
			const response = await contractService.getContracts()
			setContracts(response)
		} catch (fetchError) {
			setError(fetchError instanceof Error ? fetchError.message : "Failed to fetch contracts")
		} finally {
			setIsLoading(false)
		}
	}

	const uploadAndAnalyze = async (file: File) => {
		let intervalId: ReturnType<typeof setInterval> | null = null

		try {
			setIsLoading(true)
			setIsAnalyzing(false)
			setError(null)
			setAnalysisResult(null)
			setUploadProgress(0)

			const uploadedContract = await contractService.uploadContract(file)
			console.log("Upload result:", uploadedContract)
			setCurrentContract(uploadedContract)
			const contractId = String(uploadedContract.contract_id)
			console.log("Contract ID:", contractId)
			setUploadProgress(50)

			await contractService.analyzeContract(contractId)
			setIsAnalyzing(true)
			setUploadProgress(100)

			await new Promise<void>((resolve, reject) => {
				const checkStatus = async () => {
					try {
						if (!contractId) {
							return
						}

						const status = await contractService.getContractStatus(contractId)

						if (status.status === "completed") {
							if (intervalId) {
								clearInterval(intervalId)
							}
							resolve()
							return
						}

						if (status.status === "failed") {
							if (intervalId) {
								clearInterval(intervalId)
							}
							reject(new Error("Contract analysis failed"))
						}
					} catch (statusError) {
						if (intervalId) {
							clearInterval(intervalId)
						}
						reject(statusError)
					}
				}

				void checkStatus()
				intervalId = setInterval(() => {
					void checkStatus()
				}, 3000)
			})

			const result = await contractService.getAnalysisResults(contractId)
			setAnalysisResult(result)
			setIsAnalyzing(false)
			setContracts((currentContracts) => [uploadedContract, ...currentContracts])
		} catch (uploadError) {
			setError(uploadError instanceof Error ? uploadError.message : "Failed to upload and analyze contract")
			setIsAnalyzing(false)
		} finally {
			if (intervalId) {
				clearInterval(intervalId)
			}
			setIsLoading(false)
		}
	}

	return {
		contracts,
		currentContract,
		analysisResult,
		isLoading,
		isAnalyzing,
		error,
		uploadProgress,
		fetchContracts,
		uploadAndAnalyze,
		clearError,
	}
}

export default useContract

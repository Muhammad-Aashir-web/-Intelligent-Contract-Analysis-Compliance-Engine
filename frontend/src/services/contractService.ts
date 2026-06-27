import apiClient from "./api"

import type { AnalysisResult, Contract } from "../types/contract"

/**
 * Maps snake_case API response fields to camelCase Contract type.
 * Backend returns: id, file_name, risk_score, created_at, status, contract_type
 * Frontend expects: id, fileName, riskScore, uploadedAt, status
 */
function mapContractFromApi(raw: any): Contract {
	return {
		id: String(raw.id),
		contract_id: raw.contract_id,
		fileName: raw.file_name,
		uploadedAt: raw.created_at,
		status: raw.status,
		riskScore: raw.risk_score,
		clauses: raw.clauses,
		complianceStatus: raw.compliance_status,
	}
}

export async function uploadContract(file: File): Promise<Contract> {
	const formData = new FormData()
	formData.append("file", file)

	const response = await apiClient.post<any>("/contracts/upload", formData, {
		headers: {
			"Content-Type": "multipart/form-data",
		},
	})

	return mapContractFromApi(response.data)
}

export async function getContracts(): Promise<Contract[]> {
	const response = await apiClient.get<{ contracts: any[]; total: number }>("/contracts")
	return response.data.contracts.map(mapContractFromApi)
}

export async function getContract(id: string): Promise<Contract> {
	const response = await apiClient.get<any>(`/contracts/${id}`)
	return mapContractFromApi(response.data)
}

export async function analyzeContract(id: string): Promise<{ task_id: string }> {
	const response = await apiClient.post<{ task_id: string }>(`/contracts/${id}/analyze`, {
		contract_id: Number(id),
	})
	return response.data
}

export async function getAnalysisResults(id: string): Promise<AnalysisResult> {
	const response = await apiClient.get<AnalysisResult>(`/contracts/${id}/results`)
	return response.data
}

export async function getContractStatus(id: string): Promise<{ status: string; progress: number }> {
	const response = await apiClient.get<{ status: string; progress: number }>(`/contracts/${id}/status`)
	return response.data
}

export async function deleteContract(id: string): Promise<void> {
	await apiClient.delete(`/contracts/${id}`)
}

export async function askQuestion(
	id: string,
	question: string,
): Promise<{ answer: string }> {
	const response = await apiClient.post<{ answer: string }>(`/contracts/${id}/ask`, {
		question,
	})

	return response.data
}

const contractService = {
	uploadContract,
	getContracts,
	getContract,
	analyzeContract,
	getAnalysisResults,
	getContractStatus,
	deleteContract,
	askQuestion,
}

export default contractService

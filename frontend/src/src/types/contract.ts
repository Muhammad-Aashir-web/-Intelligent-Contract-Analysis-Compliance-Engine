export type ClauseRiskLevel = "low" | "medium" | "high" | "critical"

export type ContractStatus = "pending" | "processing" | "completed" | "failed"

export interface Clause {
	id: string
	type: string
	title: string
	content: string
	riskLevel: ClauseRiskLevel
	page?: number
	suggestions?: string[]
}

export interface Contract {
	id: string
	fileName: string
	uploadedAt: string
	status: ContractStatus
	riskScore?: number
	clauses?: Clause[]
	complianceStatus?: string
}

export interface AnalysisResult {
	contractId: string
	overallRiskScore: number
	clauses: Clause[]
	complianceIssues: Array<{
		framework: string
		issue: string
		severity: string
	}>
	recommendations: string[]
	summary: string
}

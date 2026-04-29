import type { Clause } from "./contract"

export const sampleClauses: Clause[] = [
	{
		id: "1",
		type: "Payment Terms",
		title: "Payment Schedule",
		riskLevel: "medium",
		page: 2,
		content:
			"Payment shall be made within 30 days of invoice receipt. Late payments will incur a 1.5% monthly interest charge.",
		suggestions: [
			"Consider negotiating to Net-45 payment terms",
			"Add a grace period of 5 business days",
		],
	},
	{
		id: "2",
		type: "Termination",
		title: "Termination for Convenience",
		riskLevel: "high",
		page: 5,
		content:
			"Either party may terminate this agreement with 30 days written notice without cause or penalty.",
		suggestions: [
			"Increase notice period to 90 days",
			"Add compensation clause for early termination",
		],
	},
	{
		id: "3",
		type: "Liability",
		title: "Limitation of Liability",
		riskLevel: "critical",
		page: 7,
		content:
			"In no event shall either party be liable for indirect, incidental, or consequential damages exceeding the total contract value.",
		suggestions: [
			"Define maximum liability cap clearly",
			"Exclude gross negligence from limitation clause",
		],
	},
	{
		id: "4",
		type: "Confidentiality",
		title: "Non-Disclosure Agreement",
		riskLevel: "low",
		page: 3,
		content:
			"Both parties agree to maintain strict confidentiality of all proprietary information shared during the contract period.",
		suggestions: [],
	},
	{
		id: "5",
		type: "Intellectual Property",
		title: "IP Ownership",
		riskLevel: "high",
		page: 8,
		content:
			"All work product and intellectual property created under this agreement shall be owned exclusively by the Client.",
		suggestions: [
			"Clarify ownership of pre-existing IP",
			"Add license back provision for Vendor",
		],
	},
	{
		id: "6",
		type: "Dispute Resolution",
		title: "Arbitration Clause",
		riskLevel: "medium",
		page: 10,
		content:
			"Any disputes arising from this agreement shall be resolved through binding arbitration in New York, NY.",
		suggestions: [
			"Specify arbitration rules and governing body",
			"Add mediation as first step before arbitration",
		],
	},
]
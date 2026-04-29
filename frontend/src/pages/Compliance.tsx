import Layout from "../components/layout/Layout"
import ClauseList from "../components/clauses/ClauseList"
import { sampleClauses } from "../types/sampleData"

const frameworks = [
	{ name: "GDPR", className: "bg-blue-50 border border-blue-200 rounded-lg p-4 text-center" },
	{ name: "HIPAA", className: "bg-green-50 border border-green-200 rounded-lg p-4 text-center" },
	{ name: "SOX", className: "bg-purple-50 border border-purple-200 rounded-lg p-4 text-center" },
	{ name: "CCPA", className: "bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center" },
	{ name: "GENERAL", className: "bg-gray-50 border border-gray-200 rounded-lg p-4 text-center" },
]

function Compliance() {
	return (
		<Layout title="Compliance">
			<div className="space-y-8">
				<div>
					<h2 className="text-2xl font-semibold text-gray-900 mb-4">Compliance Frameworks</h2>
					<div className="grid grid-cols-5 gap-4">
						{frameworks.map((framework) => (
							<div key={framework.name} className={framework.className}>
								<div className="font-semibold text-gray-800">{framework.name}</div>
								<div className="text-sm text-gray-500 mt-1">Not Checked</div>
							</div>
						))}
					</div>
				</div>

				<div>
					<h2 className="text-2xl font-semibold text-gray-900 mb-4">Extracted Clauses</h2>
					<ClauseList clauses={sampleClauses} />
				</div>
			</div>
		</Layout>
	)
}

export default Compliance

import { FileText } from "lucide-react"

import Layout from "../components/layout/Layout"

function Contracts() {
	return (
		<Layout title="Contracts">
			<div className="space-y-6">
				<div className="flex items-center justify-between">
					<h2 className="text-2xl font-semibold text-gray-900">Contracts</h2>
					<button
						type="button"
						className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
					>
						Upload Contract
					</button>
				</div>

				<div className="bg-white rounded-xl shadow-sm p-16 flex flex-col items-center justify-center text-center">
					<FileText size={48} className="text-gray-400" />
					<p className="mt-4 text-lg font-medium text-gray-700">No contracts yet</p>
					<p className="mt-1 text-sm text-gray-500">Upload your first contract to begin analysis</p>
				</div>
			</div>
		</Layout>
	)
}

export default Contracts

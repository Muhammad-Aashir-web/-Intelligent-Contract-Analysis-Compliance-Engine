import Sidebar from './Sidebar'
import Header from './Header'
import { ReactNode } from 'react'

interface LayoutProps {
	children: ReactNode
	title: string
}

export default function Layout({ children, title }: LayoutProps) {
	return (
		<div className="flex h-screen bg-gray-50">
			<div className="w-64 flex-shrink-0">
				<Sidebar />
			</div>
			<div className="flex-1 flex flex-col overflow-hidden">
				<Header title={title} />
				<main className="flex-1 overflow-y-auto p-6">
					{children}
				</main>
			</div>
		</div>
	)
}

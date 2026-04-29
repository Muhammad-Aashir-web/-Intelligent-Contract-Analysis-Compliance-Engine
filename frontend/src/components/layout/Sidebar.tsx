import {
	AlertTriangle,
	FileText,
	LayoutDashboard,
	Settings,
	Shield,
	type LucideIcon,
} from "lucide-react"
import { useLocation, useNavigate } from "react-router-dom"

type NavItem = {
	label: string
	path: string
	icon: LucideIcon
}

const navItems: NavItem[] = [
	{ label: "Dashboard", path: "/", icon: LayoutDashboard },
	{ label: "Contracts", path: "/contracts", icon: FileText },
	{ label: "Compliance", path: "/compliance", icon: Shield },
	{ label: "Risk Analysis", path: "/risk", icon: AlertTriangle },
	{ label: "Settings", path: "/settings", icon: Settings },
]

function Sidebar() {
	const location = useLocation()
	const navigate = useNavigate()

	const isActive = (path: string): boolean => {
		if (path === "/") {
			return location.pathname === "/"
		}
		return location.pathname === path || location.pathname.startsWith(`${path}/`)
	}

	return (
		<aside className="fixed left-0 top-0 w-64 h-screen bg-blue-900">
			<div className="py-6 px-6 border-b border-blue-800">
				<h1 className="text-white font-bold text-xl">Contract AI</h1>
				<p className="text-blue-300 text-sm mt-1">Intelligence Platform</p>
			</div>

			<nav className="py-4">
				{navItems.map((item) => {
					const Icon = item.icon
					const active = isActive(item.path)

					return (
						<div
							key={item.path}
							className={`flex items-center gap-3 px-6 py-3 text-blue-100 cursor-pointer ${
								active ? "bg-blue-700 text-white" : ""
							}`}
							onClick={() => navigate(item.path)}
							role="button"
							tabIndex={0}
							onKeyDown={(event) => {
								if (event.key === "Enter" || event.key === " ") {
									event.preventDefault()
									navigate(item.path)
								}
							}}
						>
							<Icon size={18} />
							<span>{item.label}</span>
						</div>
					)
				})}
			</nav>
		</aside>
	)
}

export default Sidebar
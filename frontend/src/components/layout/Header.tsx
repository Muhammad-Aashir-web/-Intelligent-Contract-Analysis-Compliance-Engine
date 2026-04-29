import { BellIcon } from "lucide-react"

type HeaderProps = {
	title: string
}

function Header({ title }: HeaderProps) {
	return (
		<div className="h-16 bg-white shadow-sm flex items-center justify-between px-6 w-full border-b border-gray-200">
			<h1 className="text-xl font-semibold text-gray-800">{title}</h1>

			<div className="flex items-center gap-4">
				<div className="relative">
					<BellIcon size={20} className="text-gray-600" />
					<span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full" />
				</div>

				<div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
					CA
				</div>
			</div>
		</div>
	)
}

export default Header
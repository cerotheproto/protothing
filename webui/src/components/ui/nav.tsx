import {
     ScanEye, // preview
     LayoutGrid, // apps
     FolderOpen, // assets
     Rocket, // events
        Sparkles, // effects
        Settings, // settings

} from "lucide-react"; 

export const navItems = [
    {
        title: "Preview",
        href: "/preview",
        icon: ScanEye,
    },
    {
        title: "Applications",
        href: "/apps",
        icon: LayoutGrid,
    },
    {
        title: "Assets",
        href: "/assets",
        icon: FolderOpen,
    },
    {
        title: "Events",
        href: "/events",
        icon: Rocket,
    },
    {
        title: "Effects",
        href: "/effects",
        icon: Sparkles,
    },
    {
        title: "Settings",
        href: "/settings",
        icon: Settings,
    },
];

export default function Nav() {
    return (
        <nav className="fixed bottom-0 left-0 right-0 z-40 flex justify-between px-2 py-2 md:fixed md:top-0 md:bottom-0 md:left-0 md:w-16 md:flex-col md:justify-start md:items-center md:py-4 bg-[--background] border-t md:border-t-0 md:border-r border-border bg-black">
            {navItems.map((item) => (
                <a
                    key={item.href}
                    href={item.href}
                    aria-label={item.title}
                    className="flex-1 flex items-center justify-center px-2 py-1 text-gray-300 hover:bg-transparent md:flex-none md:mb-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                >
                    <item.icon className="w-7 h-7 md:w-6 md:h-6" />
                </a>
            ))}
        </nav>
    );
}
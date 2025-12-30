import './globals.css';
import Nav from '../components/ui/nav';
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className='dark'>
        <main className="min-h-screen pb-14 md:pb-0 md:pl-16 flex flex-col bg-background">
          {children}
        </main>
        <Nav />
      </body>
    </html>
  );
}

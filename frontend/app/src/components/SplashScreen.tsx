export default function SplashScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-black p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-100 to-gray-300 dark:from-gray-900 dark:to-black">
      <img
        src="finanze-fg.svg"
        alt="Finanze Logo"
        className="w-64 h-64 animate-breathing drop-shadow"
      />
    </div>
  )
}

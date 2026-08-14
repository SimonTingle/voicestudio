/**
 * Keep the desktop shell from accidentally navigating away while preserving
 * browser-native affordances such as selecting text, copying, and context
 * menus. The latter are especially important in the web build.
 */
export function installDesktopInteractionGuards({ onDrop }) {
  const handleKeyDown = (event) => {
    if (!event.metaKey && !event.ctrlKey) return;
    if (['r', 'p', '=', '-', '+'].includes(event.key.toLowerCase())) event.preventDefault();
  };
  const handleWheel = (event) => {
    if (event.ctrlKey) event.preventDefault();
  };
  const handleDrop = (event) => {
    event.preventDefault();
    const file = event.dataTransfer?.files[0];
    if (file) onDrop(file);
  };
  const handleDragOver = (event) => event.preventDefault();

  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('wheel', handleWheel, { passive: false });
  window.addEventListener('drop', handleDrop);
  window.addEventListener('dragover', handleDragOver);

  return () => {
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('wheel', handleWheel);
    window.removeEventListener('drop', handleDrop);
    window.removeEventListener('dragover', handleDragOver);
  };
}

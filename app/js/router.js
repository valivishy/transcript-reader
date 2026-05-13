const routes = {};
let currentView = null;

function register(path, handler) {
  routes[path] = handler;
}

function navigate(path) {
  window.location.hash = path;
}

function getCurrentPath() {
  return window.location.hash.slice(1) || '/';
}

async function render() {
  const path = getCurrentPath();
  const app = document.getElementById('app');

  let handler = routes[path];
  if (!handler) {
    const dynamicMatch = Object.keys(routes).find((route) => {
      if (!route.includes(':')) return false;
      const routeParts = route.split('/');
      const pathParts = path.split('/');
      if (routeParts.length !== pathParts.length) return false;
      return routeParts.every((part, i) => part.startsWith(':') || part === pathParts[i]);
    });
    handler = dynamicMatch ? routes[dynamicMatch] : null;
  }

  if (!handler) {
    app.innerHTML = '<p>Page not found</p>';
    return;
  }

  const params = extractParams(handler, path);
  const content = await handler(params);
  app.innerHTML = content;
  currentView = path;
}

function extractParams(handler, path) {
  const routeKey = Object.keys(routes).find((r) => routes[r] === handler);
  if (!routeKey || !routeKey.includes(':')) return {};
  const routeParts = routeKey.split('/');
  const pathParts = path.split('/');
  const params = {};
  routeParts.forEach((part, i) => {
    if (part.startsWith(':')) {
      params[part.slice(1)] = decodeURIComponent(pathParts[i]);
    }
  });
  return params;
}

function init() {
  window.addEventListener('hashchange', render);
  render();
}

export { register, navigate, init, getCurrentPath, render };

'use strict';
(() => {
  let loading;
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Could not load ${src}`));
      document.head.append(script);
    });
  }
  function showError(error) {
    const node = document.getElementById('api-docs-error');
    node.hidden = false;
    node.textContent = `API reference could not be loaded: ${error.message}. Open the OpenAPI JSON to inspect the contract.`;
  }
  window.mountApiDocs = () => {
    if (window.ruviewApiDocs) return Promise.resolve(window.ruviewApiDocs);
    if (!loading) {
      loading = (async () => {
        if (!document.querySelector('link[data-api-docs-style]')) {
          const style = document.createElement('link');
          style.rel = 'stylesheet';
          style.href = '/swagger-ui.css';
          style.dataset.apiDocsStyle = 'true';
          document.head.append(style);
        }
        await loadScript('/swagger-ui-bundle.js');
        window.ruviewApiDocs = SwaggerUIBundle({
          url: '/api/openapi.json',
          dom_id: '#swagger-ui',
          deepLinking: true,
          docExpansion: 'list',
          displayRequestDuration: true,
          persistAuthorization: false,
          validatorUrl: 'none',
          tryItOutEnabled: true,
          supportedSubmitMethods: ['get', 'post', 'put', 'patch', 'delete'],
          filter: true,
          layout: 'BaseLayout',
          defaultModelsExpandDepth: -1
        });
        return window.ruviewApiDocs;
      })().catch(error => {
        loading = null;
        showError(error);
        return null;
      });
    }
    return loading;
  };
})();

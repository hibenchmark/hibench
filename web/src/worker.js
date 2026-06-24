export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.hostname === 'www.hibench.dev') {
      url.protocol = 'https:';
      url.hostname = 'hibench.dev';
      return Response.redirect(url.toString(), 301);
    }

    return env.ASSETS.fetch(request);
  },
};
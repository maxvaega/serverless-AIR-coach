// ATTENZIONE: non è un componente del sito
// Proxy tra dominio personalizzato e servizi su Vercel (API Python) e Cloudflare Pages (sito Next.js)
//
//URL: https://air-coach-proxy.aistruttore.workers.dev/
// Serve per fare da proxy tra il dominio personalizzato e i servizi su Vercel e Cloudflare Pages

export default {
  async fetch(request) {
    const startTime = Date.now();
    const url = new URL(request.url);
    const requestId = crypto.randomUUID();

    // Log richiesta iniziale
    console.log(JSON.stringify({
      type: 'request',
      requestId,
      timestamp: new Date().toISOString(),
      method: request.method,
      url: request.url,
      pathname: url.pathname,
      userAgent: request.headers.get('user-agent'),
      ip: request.headers.get('cf-connecting-ip')
    }));

    if (url.pathname.startsWith('/api/') || url.pathname.endsWith('.json')) {
      // Proxy verso API Python su Vercel
      const apiUrl = `https://air-coach.vercel.app${url.pathname}${url.search}`;

      // Leggi il body della richiesta per il logging
      let requestBody = null;
      if (request.method !== 'GET' && request.method !== 'HEAD') {
        requestBody = await request.clone().text();
      }

      // Log chiamata API
      console.log(JSON.stringify({
        type: 'api_call',
        requestId,
        destination: apiUrl,
        hasAuth: !!request.headers.get('authorization'),
        endpoint: url.pathname,
        method: request.method,
        requestBody: requestBody,
        contentType: request.headers.get('content-type'),
        contentLength: request.headers.get('content-length')
      }));

      // Crea nuovi headers puliti
      const newHeaders = new Headers();
      newHeaders.set('accept', 'application/json');
      newHeaders.set('content-type', 'application/json');

      // Copia alcuni headers importanti dalla richiesta originale
      if (request.headers.get('authorization')) {
        newHeaders.set('authorization', request.headers.get('authorization'));
      }

      const newRequest = new Request(apiUrl, {
        method: request.method,
        headers: newHeaders,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : null
      });

      const response = await fetch(newRequest);

      const contentType = response.headers.get('content-type');
      const isSSE = contentType && contentType.includes('text/event-stream');

      if (isSSE) {
        // === STREAMING SSE CON LOGGING ASINCRONO ===

        // Buffer per accumulare i chunk
        let accumulatedChunks = [];
        let totalBytes = 0;

        // TransformStream che passa i chunk al client e li accumula per il log
        const { readable, writable } = new TransformStream({
          transform(chunk, controller) {
            // Passa immediatamente il chunk al client (streaming real-time)
            controller.enqueue(chunk);

            // Accumula il chunk per il logging successivo
            accumulatedChunks.push(new Uint8Array(chunk));
            totalBytes += chunk.byteLength;
          },

          flush() {
            // Quando lo stream è completato, esegui il logging
            try {
              // Ricostruisci il body completo
              const completeBody = new Uint8Array(totalBytes);
              let offset = 0;
              for (const chunk of accumulatedChunks) {
                completeBody.set(chunk, offset);
                offset += chunk.byteLength;
              }

              const bodyText = new TextDecoder().decode(completeBody);

              // Log formattato per SSE (sostituisce newline per leggibilità)
              const logResponseBody = bodyText
                .replace(/\n\n/g, '\\n\\n')
                .replace(/\n/g, '\\n');

              // Log completo della risposta SSE
              console.log(JSON.stringify({
                type: 'api_response',
                requestId,
                status: response.status,
                statusText: response.statusText,
                duration: Date.now() - startTime,
                endpoint: url.pathname,
                responseBody: logResponseBody,
                responseSize: bodyText.length,
                isSSE: true,
                streamCompleted: true,
                responseHeaders: {
                  contentType: response.headers.get('content-type'),
                  contentLength: response.headers.get('content-length'),
                  cacheControl: response.headers.get('cache-control')
                }
              }));

              // Libera memoria
              accumulatedChunks = null;
            } catch (error) {
              console.error(JSON.stringify({
                type: 'sse_logging_error',
                requestId,
                error: error.message,
                endpoint: url.pathname
              }));
            }
          }
        });

        // Avvia il piping dello stream (non-blocking)
        response.body.pipeTo(writable);

        // Restituisci immediatamente la response con lo stream readable
        return new Response(readable, {
          status: response.status,
          statusText: response.statusText,
          headers: {
            ...Object.fromEntries(response.headers),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
          }
        });

      } else {
        // === RISPOSTA NON-SSE (comportamento originale) ===

        const responseBody = await response.clone().text();

        // Log risposta API
        console.log(JSON.stringify({
          type: 'api_response',
          requestId,
          status: response.status,
          statusText: response.statusText,
          duration: Date.now() - startTime,
          endpoint: url.pathname,
          responseBody: responseBody,
          responseSize: responseBody.length,
          isSSE: false,
          responseHeaders: {
            contentType: response.headers.get('content-type'),
            contentLength: response.headers.get('content-length'),
            cacheControl: response.headers.get('cache-control')
          }
        }));

        // Aggiungi headers CORS alla risposta
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: {
            ...Object.fromEntries(response.headers),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
          }
        });
      }

    } else {
      // Proxy verso sito Next.js su Cloudflare Pages
      const siteUrl = `https://website-air-coach.pages.dev${url.pathname}${url.search}`;

      // Log traffico sito
      console.log(JSON.stringify({
        type: 'site_request',
        requestId,
        destination: `website-air-coach.pages.dev${url.pathname}`,
        pathname: url.pathname
      }));

      const response = await fetch(siteUrl, {
        method: request.method,
        headers: request.headers,
        body: request.body
      });

      // Log risposta sito
      console.log(JSON.stringify({
        type: 'site_response',
        requestId,
        status: response.status,
        duration: Date.now() - startTime,
        pathname: url.pathname
      }));

      return response;
    }
  }
}
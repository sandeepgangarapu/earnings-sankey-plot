function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
}


export function statementFilename(statement, extension) {
  return `${statement.ticker.toLowerCase()}-${statement.fiscal_year}-${statement.period.toLowerCase()}-sankey.${extension}`;
}


export function serializeStatement(statement) {
  return `${JSON.stringify(statement, null, 2)}\n`;
}


export function buildStandaloneHtml(result) {
  const title = `${escapeHtml(result.statement.company)} earnings Sankey`;
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <style>body{margin:0;background:#edf2ee;padding:24px}svg{width:100%;height:auto;background:#fbfcfa;border-radius:14px}</style>
</head>
<body>${result.svg}</body>
</html>
`;
}


export function buildShareMetadata(statement, pageUrl) {
  return {
    title: `${statement.company} earnings Sankey`,
    text: `See ${statement.company} (${statement.ticker}) · ${statement.period} FY${statement.fiscal_year} earnings as a Sankey diagram.`,
    url: pageUrl,
  };
}


export function buildSocialShareUrls(metadata) {
  const linkedin = new URL('https://www.linkedin.com/sharing/share-offsite/');
  linkedin.searchParams.set('url', metadata.url);

  const x = new URL('https://twitter.com/intent/tweet');
  x.searchParams.set('text', metadata.text);
  x.searchParams.set('url', metadata.url);

  const facebook = new URL('https://www.facebook.com/sharer/sharer.php');
  facebook.searchParams.set('u', metadata.url);

  return {
    linkedin: linkedin.href,
    x: x.href,
    facebook: facebook.href,
  };
}


export function buildNativeShareData(metadata, svg, filename, environment = {}) {
  if (typeof environment.File !== 'function' || typeof environment.canShare !== 'function') {
    return { ...metadata };
  }

  try {
    const file = new environment.File([svg], filename, { type: 'image/svg+xml' });
    const candidate = { ...metadata, files: [file] };
    return environment.canShare(candidate) ? candidate : { ...metadata };
  } catch {
    return { ...metadata };
  }
}


function svgViewBoxSize(svg) {
  const match = String(svg).match(/\bviewBox\s*=\s*["']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)\s*["']/i);
  if (match) {
    const width = Number(match[1]);
    const height = Number(match[2]);
    if (Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0) return { width, height };
  }
  return { width: 1280, height: 720 };
}


export function renderSvgToPng(svg, environment = {}, scale = 2) {
  return new Promise((resolve, reject) => {
    const BlobConstructor = environment.Blob;
    const ImageConstructor = environment.Image;
    const documentRef = environment.document;
    const urlApi = environment.URL;
    let objectUrl = null;

    const cleanup = () => {
      if (objectUrl) {
        urlApi.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    };
    const fail = () => {
      cleanup();
      reject(new Error('The chart could not be rendered as a PNG.'));
    };

    try {
      if (!BlobConstructor || !ImageConstructor || !documentRef?.createElement || !urlApi?.createObjectURL) {
        fail();
        return;
      }
      const svgBlob = new BlobConstructor([svg], { type: 'image/svg+xml' });
      objectUrl = urlApi.createObjectURL(svgBlob);
      const image = new ImageConstructor();
      image.onload = () => {
        try {
          const { width, height } = svgViewBoxSize(svg);
          const canvas = documentRef.createElement('canvas');
          canvas.width = Math.round(width * scale);
          canvas.height = Math.round(height * scale);
          const context = canvas.getContext('2d');
          if (!context || typeof canvas.toBlob !== 'function') {
            fail();
            return;
          }
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          canvas.toBlob((pngBlob) => {
            cleanup();
            if (pngBlob) resolve(pngBlob);
            else reject(new Error('The chart could not be rendered as a PNG.'));
          }, 'image/png');
        } catch {
          fail();
        }
      };
      image.onerror = fail;
      image.src = objectUrl;
    } catch {
      fail();
    }
  });
}


export async function copyPngBlob(pngSource, environment = {}) {
  if (typeof environment.ClipboardItem !== 'function' || typeof environment.clipboard?.write !== 'function') {
    return false;
  }
  try {
    const item = new environment.ClipboardItem({ 'image/png': pngSource });
    await environment.clipboard.write([item]);
    return true;
  } catch {
    return false;
  }
}


export function selectResultMode(requestedMode, tabs, panels) {
  const modes = Array.from(tabs, (tab) => tab.dataset.resultMode);
  const mode = modes.includes(requestedMode) ? requestedMode : (modes.includes('chart') ? 'chart' : modes[0]);

  Array.from(tabs).forEach((tab) => {
    const selected = tab.dataset.resultMode === mode;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  Array.from(panels).forEach((panel) => {
    panel.hidden = panel.dataset.resultPanel !== mode;
  });

  return mode;
}


export async function copyText(text, environment = {}) {
  if (environment.clipboard?.writeText) {
    try {
      await environment.clipboard.writeText(text);
      return true;
    } catch {
      // Permission failures can still succeed through the selection fallback.
    }
  }

  const documentRef = environment.document;
  if (!documentRef?.body || !documentRef.createElement || !documentRef.execCommand) return false;

  let textarea = null;
  try {
    textarea = documentRef.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    documentRef.body.append(textarea);
    textarea.select();
    return Boolean(documentRef.execCommand('copy'));
  } catch {
    return false;
  } finally {
    try { textarea?.remove(); } catch { /* Cleanup failure must not mask copy status. */ }
  }
}

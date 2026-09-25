let cachedApiBaseUrl = null;

export async function getApiBaseUrl() {
  if (cachedApiBaseUrl) {
    return cachedApiBaseUrl;
  }

  const res = await fetch('/config.json');
  const config = await res.json();
  cachedApiBaseUrl = config.API_BASE_URL;
  return cachedApiBaseUrl;
}
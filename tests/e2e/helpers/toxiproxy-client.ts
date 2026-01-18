/**
 * Toxiproxy client for E2E tests.
 *
 * Provides methods to create proxies and inject network faults.
 *
 * @see https://github.com/Shopify/toxiproxy
 */

const TOXIPROXY_API_URL =
  process.env.TOXIPROXY_API_URL ||
  "http://buun-curator-toxiproxy.buun-curator-e2e:8474";

interface Proxy {
  name: string;
  listen: string;
  upstream: string;
  enabled: boolean;
}

interface Toxic {
  name: string;
  type: string;
  stream: "upstream" | "downstream";
  toxicity: number;
  attributes: Record<string, unknown>;
}

/**
 * Create a new proxy in Toxiproxy.
 *
 * If a proxy with the same name already exists, it will be deleted first.
 */
export async function createProxy(
  name: string,
  listen: string,
  upstream: string,
): Promise<Proxy> {
  const response = await fetch(`${TOXIPROXY_API_URL}/proxies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, listen, upstream, enabled: true }),
  });

  if (response.status === 409) {
    // Proxy already exists, delete and recreate
    await deleteProxy(name);
    return createProxy(name, listen, upstream);
  }

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create proxy: ${error}`);
  }

  return response.json();
}

/**
 * Delete a proxy from Toxiproxy.
 */
export async function deleteProxy(name: string): Promise<void> {
  const response = await fetch(`${TOXIPROXY_API_URL}/proxies/${name}`, {
    method: "DELETE",
  });

  if (!response.ok && response.status !== 404) {
    const error = await response.text();
    throw new Error(`Failed to delete proxy: ${error}`);
  }
}

/**
 * Get all proxies from Toxiproxy.
 */
export async function getProxies(): Promise<Record<string, Proxy>> {
  const response = await fetch(`${TOXIPROXY_API_URL}/proxies`);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get proxies: ${error}`);
  }

  return response.json();
}

/**
 * Add a toxic to a proxy.
 */
export async function addToxic(
  proxyName: string,
  toxic: Omit<Toxic, "name"> & { name?: string },
): Promise<Toxic> {
  const response = await fetch(
    `${TOXIPROXY_API_URL}/proxies/${proxyName}/toxics`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toxic),
    },
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to add toxic: ${error}`);
  }

  return response.json();
}

/**
 * Remove a toxic from a proxy.
 */
export async function removeToxic(
  proxyName: string,
  toxicName: string,
): Promise<void> {
  const response = await fetch(
    `${TOXIPROXY_API_URL}/proxies/${proxyName}/toxics/${toxicName}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok && response.status !== 404) {
    const error = await response.text();
    throw new Error(`Failed to remove toxic: ${error}`);
  }
}

/**
 * Remove all toxics from a proxy.
 */
export async function removeAllToxics(proxyName: string): Promise<void> {
  const response = await fetch(
    `${TOXIPROXY_API_URL}/proxies/${proxyName}/toxics`,
  );

  if (!response.ok) {
    return;
  }

  const toxics: Toxic[] = await response.json();
  await Promise.all(toxics.map((t) => removeToxic(proxyName, t.name)));
}

// --- Convenience methods for common toxics ---

/**
 * Add timeout toxic - stops all data and optionally closes connection.
 *
 * @param proxyName - Name of the proxy
 * @param timeout - Timeout in milliseconds (0 = never close, just drop data)
 */
export async function addTimeoutToxic(
  proxyName: string,
  timeout: number,
): Promise<Toxic> {
  return addToxic(proxyName, {
    name: "timeout",
    type: "timeout",
    stream: "downstream",
    toxicity: 1,
    attributes: { timeout },
  });
}

/**
 * Add latency toxic - adds delay to data.
 *
 * @param proxyName - Name of the proxy
 * @param latency - Latency in milliseconds
 * @param jitter - Random jitter in milliseconds
 */
export async function addLatencyToxic(
  proxyName: string,
  latency: number,
  jitter = 0,
): Promise<Toxic> {
  return addToxic(proxyName, {
    name: "latency",
    type: "latency",
    stream: "downstream",
    toxicity: 1,
    attributes: { latency, jitter },
  });
}

/**
 * Add bandwidth toxic - limits bandwidth.
 *
 * @param proxyName - Name of the proxy
 * @param rate - Rate in KB/s
 */
export async function addBandwidthToxic(
  proxyName: string,
  rate: number,
): Promise<Toxic> {
  return addToxic(proxyName, {
    name: "bandwidth",
    type: "bandwidth",
    stream: "downstream",
    toxicity: 1,
    attributes: { rate },
  });
}

/**
 * Add slow_close toxic - delays connection close.
 *
 * @param proxyName - Name of the proxy
 * @param delay - Delay in milliseconds before connection closes
 */
export async function addSlowCloseToxic(
  proxyName: string,
  delay: number,
): Promise<Toxic> {
  return addToxic(proxyName, {
    name: "slow_close",
    type: "slow_close",
    stream: "downstream",
    toxicity: 1,
    attributes: { delay },
  });
}

/**
 * Add reset_peer toxic - simulates TCP RST (connection reset).
 *
 * @param proxyName - Name of the proxy
 * @param timeout - Time before RST in milliseconds
 */
export async function addResetPeerToxic(
  proxyName: string,
  timeout: number,
): Promise<Toxic> {
  return addToxic(proxyName, {
    name: "reset_peer",
    type: "reset_peer",
    stream: "downstream",
    toxicity: 1,
    attributes: { timeout },
  });
}

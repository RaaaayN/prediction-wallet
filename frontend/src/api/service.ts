const API_BASE = '';

export class ApiError extends Error {
  status: number;

  statusText: string;

  constructor(message: string, status: number, statusText: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
  }
}

export class ApiService {
  private static getHeaders(): Record<string, string> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const apiKey = localStorage.getItem('prediction_wallet_api_key');
    if (apiKey) {
      headers['X-API-KEY'] = apiKey;
    }
    return headers;
  }

  static async get<T>(path: string): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, {
      headers: ApiService.getHeaders(),
    });
    if (!resp.ok) {
      throw new ApiError(`API Error: ${resp.status} ${resp.statusText}`, resp.status, resp.statusText);
    }
    return (await resp.json()) as T;
  }

  static async postJson<T>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: ApiService.getHeaders(),
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      throw new ApiError(`API Error: ${resp.status} ${resp.statusText}`, resp.status, resp.statusText);
    }
    return (await resp.json()) as T;
  }

  static async post<T>(path: string, body: unknown): Promise<T> {
    return ApiService.postJson<T>(path, body);
  }

  static stream(
    path: string,
    body: unknown,
    onMessage: (data: Record<string, unknown>) => void,
    onComplete: (exitCode: number) => void,
  ): void {
    void fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: ApiService.getHeaders(),
      body: JSON.stringify(body),
    })
      .then(async (resp) => {
        if (!resp.body) return;
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const msg = JSON.parse(line.slice(6)) as Record<string, unknown>;
              onMessage(msg);
              if (msg.exit !== undefined) {
                onComplete(Number(msg.exit));
              }
            } catch {
              console.error('Error parsing stream message');
            }
          }
        }
      })
      .catch((err: Error) => {
        console.error('Stream error:', err);
        onMessage({ line: `Error: ${err.message}` });
        onComplete(1);
      });
  }
}

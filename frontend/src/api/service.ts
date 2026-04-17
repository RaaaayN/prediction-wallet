const API_BASE = ''; // Same origin

export class ApiService {
  static async get<T>(path: string): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`);
    if (!resp.ok) {
      throw new Error(`API Error: ${resp.status} ${resp.statusText}`);
    }
    return resp.json();
  }

  static async post<T>(path: string, body: any): Promise<T> {
    const resp = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      throw new Error(`API Error: ${resp.status} ${resp.statusText}`);
    }
    return resp.json();
  }

  static stream(path: string, body: any, onMessage: (data: any) => void, onComplete: (exitCode: number) => void) {
    fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(async (resp) => {
      if (!resp.body) return;
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            onMessage(msg);
            if (msg.exit !== undefined) {
              onComplete(msg.exit);
            }
          } catch (e) {
            console.error('Error parsing stream message:', e);
          }
        }
      }
    }).catch(err => {
      console.error('Stream error:', err);
      onMessage({ line: `Error: ${err.message}` });
      onComplete(1);
    });
  }
}

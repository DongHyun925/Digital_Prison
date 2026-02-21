import { useState, useEffect, useRef } from 'react'
import Terminal from './components/Terminal'
import VisualPanel from './components/VisualPanel'
import StatusPanel from './components/StatusPanel'
import { soundEngine } from './utils/SoundEngine'


const getBaseUrl = () => {
  let url = (import.meta.env.VITE_API_URL || 'http://localhost:5000').trim().replace(/\/$/, '');
  if (!url.startsWith('http')) {
    url = `https://${url}`;
  }
  return url;
};
const API_URL = getBaseUrl();

function App() {
  const [logs, setLogs] = useState([])
  const [image, setImage] = useState(null)
  const [status, setStatus] = useState("SYSTEM OFFLINE")
  const [inventory, setInventory] = useState([])
  const [location, setLocation] = useState("UNKNOWN")
  const [loading, setLoading] = useState(false)
  const [audioEnabled, setAudioEnabled] = useState(false)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('gemini_api_key') || '')

  useEffect(() => {
    localStorage.setItem('gemini_api_key', apiKey)
  }, [apiKey])

  const addLog = (newLogs, replace = false) => {
    if (!newLogs || !Array.isArray(newLogs)) {
      console.warn("Invalid logs received:", newLogs);
      return;
    }

    if (replace) {
      setLogs(newLogs)
    } else {
      setLogs(prev => [...prev, ...newLogs])
    }

    // Process side effects from logs (images, status updates)
    newLogs.forEach(log => {
      if (!log) return;
      if (log.type === 'image') {
        setImage(log)
      }
      if (log.type === 'ui_update') {
        setStatus(log.status || "SYSTEM STABLE")
        setInventory(log.inventory || [])
        if (log.location) setLocation(log.location)
      }
    })
  }

  const startGame = async () => {
    setLoading(true)
    console.log("GAME INIT: Attempting connection to:", API_URL)
    try {
      // Basic ping test first to diagnose TypeError: Failed to fetch
      console.log("PING: Testing connection to /api/ping...");
      await fetch(`${API_URL}/api/ping`).then(r => console.log("PING SUCCESS:", r.status)).catch(e => console.error("PING FAILED:", e));

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // Increased to 60s for Render cold start

      const res = await fetch(`${API_URL}/api/init`, {
        method: 'POST',
        headers: { 'X-Gemini-API-Key': apiKey },
        signal: controller.signal
      })
      clearTimeout(timeoutId);

      console.log("GAME INIT: Response received, status:", res.status)
      if (!res.ok) throw new Error(`HTTP Error: ${res.status}`)

      const data = await res.json()
      console.log("GAME INIT: Data parsed:", data)

      if (data && data.logs) {
        addLog(data.logs, true)
      } else {
        throw new Error("Invalid response format from server")
      }
    } catch (err) {
      console.error("GAME INIT FAILURE:", err)
      let errorMsg = err.message;
      if (err.name === 'AbortError') errorMsg = "서버 응답 속도가 너무 느립니다 (약 60초 소요).";
      if (err.message === "Failed to fetch") {
        errorMsg = `서버 연결 실패. [${API_URL}] 주소에 접속할 수 없습니다. (상세: ${err.toString()})`;
      }

      addLog([{
        agent: "SYSTEM",
        text: `FATAL: ${errorMsg}`,
        type: "error"
      }])
    }
    setLoading(false)
  }

  // Sector 0 Local Logic for "Immediate" feel
  const LOCAL_LOGIC = {
    "0": { // Sector 0
      "침대": "매트리스 밑을 뒤져 [휘어진 철사]를 찾았습니다. (로컬 데이터 확인)",
      "바닥": "먼지 구덩이 속에 [더러운 렌즈]가 떨어져 있습니다. (로컬 데이터 확인)",
      "터미널": "전원이 들어오지 않습니다. 내부 회로가 끊어져 있습니다. (로컬 데이터 확인)",
      "유니폼": "입고 있는 죄수복입니다. 낡았지만 튼튼합니다. (로컬 데이터 확인)",
      "조사": "주변을 살펴봅니다. 차가운 금속 벽과 몇 가지 사물이 보입니다. (로컬 응답 활성)"
    }
  }

  const sendCommand = async (text) => {
    if (!text.trim()) return
    setLogs(prev => [...prev, { agent: "USER", text, type: "user_input" }])

    // Immediate Local Feedback (Optimistic UI)
    const sector0 = LOCAL_LOGIC["0"];
    for (const key in sector0) {
      if (text.includes(key)) {
        addLog([{ agent: "SYSTEM", text: `[LOCAL_ACK]: ${sector0[key]}`, type: "success" }])
        break;
      }
    }

    setLoading(true)
    console.log("COMMAND SEND: Executing:", text)
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const res = await fetch(`${API_URL}/api/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Gemini-API-Key': apiKey
        },
        body: JSON.stringify({ command: text }),
        signal: controller.signal
      })
      clearTimeout(timeoutId);

      console.log("COMMAND SEND: Status:", res.status)
      if (!res.ok) {
        const errBody = await res.text();
        throw new Error(`HTTP Error: ${res.status} | Body: ${errBody}`);
      }

      const data = await res.json()
      console.log("COMMAND SEND: Success:", data)
      addLog(data.logs)
    } catch (err) {
      console.error("COMMAND SEND FAILURE:", err)
      let errorMsg = err.message;
      if (err.name === 'AbortError') errorMsg = "서버 응답 속도가 너무 느립니다 (60초 초과).";
      if (err.message === "Failed to fetch") {
        errorMsg = `서버 연결 실패 (Failed to fetch). 브라우저가 [${API_URL}] 요청을 차단했거나 서버가 응답하지 않습니다. (상세: ${err.toString()})`;
      } else {
        // Handle 500 error with JSON body from backend (Traceback inclusion)
        try {
          if (err.message.includes("| Body: ")) {
            const jsonPart = err.message.split("| Body: ")[1];
            const serverErr = JSON.parse(jsonPart);
            if (serverErr.traceback || serverErr.error_detail) {
              errorMsg = `서버 내부 오류: ${serverErr.message || serverErr.error || 'Unknown'}\n[TRACE]: ${serverErr.traceback || serverErr.error_detail}`;
            }
          }
        } catch (e) {
          console.error("Failed to parse error body:", e);
        }
      }
      addLog([{ agent: "SYSTEM", text: `❌ 연결 오류: ${errorMsg}`, type: "error" }])
    }
    setLoading(false)
  }

  const getHint = async () => {
    setLoading(true)
    console.log("HINT REQUEST: Starting...")
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // Increased to 60s

      const res = await fetch(`${API_URL}/api/hint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Gemini-API-Key': apiKey
        },
        signal: controller.signal
      })
      clearTimeout(timeoutId);

      console.log("HINT REQUEST: Status:", res.status)
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`)

      const data = await res.json()
      addLog(data.logs)
    } catch (err) {
      console.error("HINT REQUEST FAILURE:", err)
      const errorMsg = err.name === 'AbortError' ? "힌트 시스템 응답 시간 초과 (60초)." : err.message;
      addLog([{ agent: "SYSTEM", text: `⚠️ 신호 방해: ${errorMsg}`, type: "error" }])
    }
    setLoading(false)
  }

  useEffect(() => {
    startGame()
  }, [])

  // Audio Logic: Trigger theme change on location change
  useEffect(() => {
    if (location && location.includes("구역")) {
      const match = location.match(/구역 (\d+)/)
      if (match) {
        const sectorNum = parseInt(match[1])
        soundEngine.playTheme(sectorNum)
      }
    }
  }, [location])

  const toggleAudio = async () => {
    if (!audioEnabled) {
      soundEngine.init()
      await soundEngine.resume()

      // Re-trigger current theme
      if (location && location.includes("구역")) {
        const match = location.match(/구역 (\d+)/)
        if (match) {
          const sectorNum = parseInt(match[1])
          // Force theme update even if same
          soundEngine.currentTheme = null
          soundEngine.playTheme(sectorNum)
        }
      }
    }
    const muted = soundEngine.toggleMute()
    setAudioEnabled(!muted)
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/save`, {
        method: 'POST',
        headers: { 'X-Gemini-API-Key': apiKey }
      })
      const data = await res.json()
      if (data.state) {
        localStorage.setItem('digital_prison_save', JSON.stringify(data.state))
        addLog([{ agent: "SYSTEM", text: "✅ 데이터 동기화 완료. 로컬 저장소에 세션이 저장되었습니다.", type: "success" }])
      }
    } catch (err) {
      console.error("Save failed:", err)
      addLog([{ agent: "SYSTEM", text: "❌ 저장 실패: 서버 연결 확인 필요.", type: "error" }])
    }
    setLoading(false)
  }

  const handleLoad = async () => {
    const savedState = localStorage.getItem('digital_prison_save')
    if (!savedState) {
      addLog([{ agent: "SYSTEM", text: "⚠️ 로드 실패: 저장된 파일이 없습니다.", type: "warning" }])
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/load`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Gemini-API-Key': apiKey
        },
        body: JSON.stringify({ state: JSON.parse(savedState) })
      })
      const data = await res.json()
      if (data.success) {
        addLog(data.logs, true) // Replace logs on load
      }
    } catch (err) {
      console.error("Load failed:", err)
      addLog([{ agent: "SYSTEM", text: "❌ 로드 실패: 서버 연결 확인 필요.", type: "error" }])
    }
    setLoading(false)
  }

  return (
    <div className="flex h-screen w-screen bg-cyber-bg text-cyber-primary font-mono overflow-hidden">
      <div className="scanline"></div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-12 grid-rows-12 gap-4 p-4 w-full h-full z-10">

        {/* Header (Top) */}
        <header className="col-span-12 row-span-1 border-b-2 border-cyber-primary flex items-center justify-between px-4 bg-cyber-dark/80 backdrop-blur">
          <h1 className="text-2xl font-bold tracking-widest text-shadow-neon">THE DIGITAL PRISON</h1>

          <div className="flex gap-4 text-sm items-center flex-1 justify-end">
            {/* API KEY INPUT */}
            <div className="flex items-center gap-2 border border-cyber-primary/50 px-2 py-1 bg-black/40">
              <span className="text-[10px] text-cyber-primary opacity-70">GEMINI KEY:</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter API Key..."
                className="bg-transparent border-none outline-none text-[10px] w-32 text-cyber-primary placeholder:text-cyber-primary/30"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={startGame}
                disabled={loading}
                className={`px-2 py-1 border border-cyber-glitch text-[10px] hover:bg-cyber-glitch hover:text-black transition-all ${loading ? 'opacity-50 animate-pulse' : ''}`}
              >
                {loading ? 'CONNECTING...' : 'RECONNECT'}
              </button>
              <button
                onClick={handleSave}
                className="px-2 py-1 border border-cyber-primary text-[10px] hover:bg-cyber-primary hover:text-black transition-all"
              >
                SAVE
              </button>
              <button
                onClick={handleLoad}
                className="px-2 py-1 border border-cyber-primary text-[10px] hover:bg-cyber-primary hover:text-black transition-all"
              >
                LOAD
              </button>
            </div>
            <button
              onClick={toggleAudio}
              className={`px-3 py-1 border ${audioEnabled ? 'border-cyber-primary text-cyber-primary' : 'border-gray-600 text-gray-500'} font-mono text-xs hover:bg-cyber-primary/20 transition-all`}
            >
              [{audioEnabled ? 'AUDIO: ON' : 'AUDIO: OFF'}]
            </button>
            <span className="animate-pulse hidden md:block">NET: ONLINE</span>
            <span className="hidden md:block">SEC: {(location && location.includes("구역")) ? location.split("구역")[1].split(":")[0].trim().padStart(2, '0') : "00"}</span>
          </div>
        </header>

        {/* Visual Panel (Main Center-Left) */}
        <div className="col-span-12 md:col-span-8 row-span-7 border border-cyber-dark bg-black relative">
          <VisualPanel imageData={image} />
        </div>

        {/* Status Panel (Right Sidebar) */}
        <div className="col-span-12 md:col-span-4 row-span-11 border border-cyber-primary bg-cyber-dark/50 p-4">
          <StatusPanel status={status} inventory={inventory} location={location} onHint={getHint} />
        </div>

        {/* Terminal (Bottom Center-Left) */}
        <div className="col-span-12 md:col-span-8 row-span-4 border-t border-cyber-primary bg-cyber-dark/90 text-sm">
          <Terminal logs={logs} onSend={sendCommand} loading={loading} />
        </div>

      </div >
    </div >
  )
}

export default App

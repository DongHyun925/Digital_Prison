import { useState, useEffect, useRef } from 'react'
import Terminal from './components/Terminal'
import VisualPanel from './components/VisualPanel'
import StatusPanel from './components/StatusPanel'
import { soundEngine } from './utils/SoundEngine'


const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

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
      const errorMsg = err.name === 'AbortError'
        ? "서버 응답 속도가 너무 느립니다. Render 서버가 깨어나는 중일 수 있습니다 (약 60초 소요)."
        : `연결 실패: ${err.message}`;

      addLog([{
        agent: "SYSTEM",
        text: `FATAL: ${errorMsg}. [DEBUG: ${API_URL}]`,
        type: "error"
      }])
    }
    setLoading(false)
  }

  const sendCommand = async (text) => {
    if (!text.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Gemini-API-Key': apiKey
        },
        body: JSON.stringify({ command: text })
      })
      const data = await res.json()
      addLog(data.logs)
    } catch (err) {
      console.error("Failed to send command:", err)
      addLog([{ agent: "SYSTEM", text: "ERROR: Connection lost.", type: "error" }])
    }
    setLoading(false)
  }

  const getHint = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/hint`, {
        method: 'POST',
        headers: { 'X-Gemini-API-Key': apiKey }
      })
      const data = await res.json()
      addLog(data.logs)
    } catch (err) {
      console.error("Failed to get hint:", err)
      addLog([{ agent: "SYSTEM", text: "ERROR: Signal jammed.", type: "error" }])
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
            <span className="hidden md:block">SEC: {location.includes("구역") ? location.split("구역")[1].split(":")[0].trim().padStart(2, '0') : "00"}</span>
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

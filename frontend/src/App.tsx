// // import { useState } from 'react'
// // import reactLogo from './assets/react.svg'
// // import viteLogo from '/vite.svg'
// // import './App.css'

// // function App() {
// //   const [count, setCount] = useState(0)

// //   return (
// //     <>
// //       <div>
// //         <a href="https://vite.dev" target="_blank">
// //           <img src={viteLogo} className="logo" alt="Vite logo" />
// //         </a>
// //         <a href="https://react.dev" target="_blank">
// //           <img src={reactLogo} className="logo react" alt="React logo" />
// //         </a>
// //       </div>
// //       <h1>Vite + React</h1>
// //       <div className="card">
// //         <button onClick={() => setCount((count) => count + 1)}>
// //           count is {count}
// //         </button>
// //         <p>
// //           Edit <code>src/App.tsx</code> and save to test HMR
// //         </p>
// //       </div>
// //       <p className="read-the-docs">
// //         Click on the Vite and React logos to learn more
// //       </p>
// //     </>
// //   )
// // }

// // export default App
// import { useState, useEffect } from 'react';
// import { Activity, Scale, Settings } from 'lucide-react';
// import { useWebSocket } from './shared/hooks/useWebSocket';
// import { ConnectionStatus } from './shared/components/ConnectionStatus';
// import config from './config';
// import { WebSocketMessage, LiveWeightUpdate } from './shared/types';

// function App() {
//   const [currentWeight, setCurrentWeight] = useState<LiveWeightUpdate | null>(null);
  
//   // WebSocketni ulash
//   const { status, lastMessage } = useWebSocket(config.wsUrl, {
//     onConnect: () => console.log('WebSocket Connected!'),
//     onDisconnect: () => console.log('WebSocket Disconnected'),
//   });

//   // Xabar kelganda vaznni yangilash
//   useEffect(() => {
//     if (lastMessage?.type === 'weight_update' && lastMessage.data) {
//       setCurrentWeight(lastMessage.data);
//     }
//   }, [lastMessage]);

//   return (
//     <div className="min-h-screen bg-gray-50 pb-20">
//       {/* Header */}
//       <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
//         <div className="max-w-7xl mx-auto flex items-center justify-between">
//           <div className="flex items-center gap-3">
//             <div className="bg-primary-600 p-2 rounded-lg">
//               <Activity className="w-6 h-6 text-white" />
//             </div>
//             <h1 className="text-xl font-bold text-gray-900">Taurus Vision</h1>
//           </div>
          
//           <div className="flex items-center gap-4">
//             <ConnectionStatus status={status} />
//             <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-full">
//               <Settings className="w-5 h-5" />
//             </button>
//           </div>
//         </div>
//       </header>

//       {/* Main Content */}
//       <main className="max-w-7xl mx-auto px-6 py-8">
//         <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
//           {/* Chap tomon: Jonli Ko'rsatkich */}
//           <div className="space-y-6">
//             <h2 className="text-lg font-semibold text-gray-700">Live Feed</h2>
            
//             {/* Katta Karta */}
//             <div className="card relative overflow-hidden group hover:shadow-md transition-shadow">
//               <div className="absolute top-0 right-0 p-4 opacity-10">
//                 <Scale className="w-32 h-32" />
//               </div>

//               <div className="relative z-10">
//                 <div className="text-sm font-medium text-gray-500 mb-1">
//                   Current Estimate
//                 </div>
                
//                 {currentWeight ? (
//                   <div className="space-y-4">
//                     <div className="flex items-baseline gap-2">
//                       <span className="text-6xl font-bold text-gray-900 tracking-tight">
//                         {currentWeight.estimated_weight_kg.toFixed(1)}
//                       </span>
//                       <span className="text-2xl text-gray-500 font-medium">kg</span>
//                     </div>

//                     <div className="flex gap-3">
//                       <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
//                         ID: {currentWeight.animal_tag_id}
//                       </span>
//                       <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
//                         Conf: {(currentWeight.confidence_score * 100).toFixed(0)}%
//                       </span>
//                     </div>
                    
//                     <div className="text-xs text-gray-400 mt-4">
//                       Camera: {currentWeight.camera_id} • {new Date(currentWeight.timestamp).toLocaleTimeString()}
//                     </div>
//                   </div>
//                 ) : (
//                   <div className="h-40 flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
//                     <Scale className="w-8 h-8 mb-2 opacity-50" />
//                     <p>Waiting for measurements...</p>
//                     <p className="text-xs mt-1">Make sure backend is running</p>
//                   </div>
//                 )}
//               </div>
//             </div>
//           </div>

//           {/* O'ng tomon: Statistika (Hozircha bo'sh) */}
//           <div className="space-y-6">
//             <h2 className="text-lg font-semibold text-gray-700">Recent Activity</h2>
//             <div className="card h-64 flex items-center justify-center text-gray-400">
//               <p>No recent history</p>
//             </div>
//           </div>

//         </div>
//       </main>
//     </div>
//   );
// }

// export default App;

import { useState, useEffect, useMemo } from 'react';
import { Activity, Scale, Settings } from 'lucide-react';
import { useWebSocket } from './shared/hooks/useWebSocket';
import { ConnectionStatus } from './shared/components/ConnectionStatus';
// Config fayl bilan bog'liq muammo bo'lmasligi uchun to'g'ridan-to'g'ri yozamiz
// import config from './config'; 

// --- TYPES ---
interface LiveWeightUpdate {
  animal_id: number;
  animal_tag_id: string;
  estimated_weight_kg: number;
  confidence_score: number;
  camera_id: string;
  timestamp: string;
}

// -----------------------------------------------------------

function App() {
  const [currentWeight, setCurrentWeight] = useState<LiveWeightUpdate | null>(null);
  
  // 1-MUHIM O'ZGARISH: Options obyektini xotirada saqlash (useMemo)
  // Bu "Infinite Loop"ni to'xtatadi.
  const wsOptions = useMemo(() => ({
    onConnect: () => console.log('WebSocket Connected!'),
    onDisconnect: () => console.log('WebSocket Disconnected'),
  }), []); // [] - faqat bir marta yaratilsin degani

  // 2. WebSocketni ulash
  // Manzilni "api/v1/live/ws" qilib to'g'riladik
  const { status, lastMessage } = useWebSocket("ws://localhost:8000/api/v1/live/ws", wsOptions);

  // Xabar kelganda vaznni yangilash
  useEffect(() => {
    if (lastMessage?.type === 'weight_update' && lastMessage.data) {
      setCurrentWeight(lastMessage.data);
    }
  }, [lastMessage]);

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-primary-600 p-2 rounded-lg">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">Taurus Vision</h1>
          </div>
          
          <div className="flex items-center gap-4">
            <ConnectionStatus status={status} />
            <button className="p-2 text-gray-500 hover:bg-gray-100 rounded-full">
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* Chap tomon: Jonli Ko'rsatkich */}
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-gray-700">Live Feed</h2>
            
            <div className="card relative overflow-hidden group hover:shadow-md transition-shadow bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="absolute top-0 right-0 p-4 opacity-10">
                <Scale className="w-32 h-32" />
              </div>

              <div className="relative z-10">
                <div className="text-sm font-medium text-gray-500 mb-1">
                  Current Estimate
                </div>
                
                {currentWeight ? (
                  <div className="space-y-4">
                    <div className="flex items-baseline gap-2">
                      <span className="text-6xl font-bold text-gray-900 tracking-tight">
                        {currentWeight.estimated_weight_kg.toFixed(1)}
                      </span>
                      <span className="text-2xl text-gray-500 font-medium">kg</span>
                    </div>

                    <div className="flex gap-3">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        ID: {currentWeight.animal_tag_id}
                      </span>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Conf: {(currentWeight.confidence_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    
                    <div className="text-xs text-gray-400 mt-4">
                      Camera: {currentWeight.camera_id} • {new Date(currentWeight.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ) : (
                  <div className="h-40 flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                    <Scale className="w-8 h-8 mb-2 opacity-50" />
                    <p>Waiting for measurements...</p>
                    <p className="text-xs mt-1">Make sure backend is running</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* O'ng tomon: Statistika */}
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-gray-700">Recent Activity</h2>
            <div className="card h-64 flex items-center justify-center text-gray-400 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <p>No recent history</p>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;
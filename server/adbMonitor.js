// server/adbMonitor.js
const { spawn } = require('child_process');
const WebSocket = require('ws');
const axios = require('axios');

class ADBMonitor {
    constructor() {
        this.wss = null;
        this.process = null;
        this.token = null;
        this.lastHeartRate = null;
        this.lastBP = null;
        
        // ✅ استخدام متغيرات البيئة
        this.wsPort = process.env.WS_PORT || 3001;
        this.apiUrl = process.env.API_URL || 'https://livocare-backend.onrender.com';
    }

    start() {
        console.log('='.repeat(50));
        console.log('📱 ADB Monitor for Z99 Ultra / FitPro');
        console.log('='.repeat(50));
        console.log('');
        
        // ✅ التحقق من وجود ADB
        this.checkADB();
        
        // ✅ بدء WebSocket (بدون SSL للرفع، لأن السحابة تتعامل مع SSL)
        this.startWebSocketSimple();
        
        // ✅ بدء مراقبة ADB logs
        setTimeout(() => this.startADBLogcat(), 2000);
    }

    checkADB() {
        const adbCheck = spawn('adb', ['devices']);
        adbCheck.stdout.on('data', (data) => {
            const output = data.toString();
            if (output.includes('device')) {
                console.log('✅ ADB is working');
                console.log(`   Devices: ${output.split('\n')[1] || 'none'}`);
            } else {
                console.log('⚠️ No devices connected. Please connect your phone via USB');
                console.log('   Enable USB debugging on your phone');
            }
        });
        adbCheck.stderr.on('data', () => {
            console.log('❌ ADB not found. Please install ADB and add to PATH');
        });
    }

    // ✅ نسخة مبسطة للرفع (بدون SSL)
    startWebSocketSimple() {
        this.wss = new WebSocket.Server({ port: this.wsPort, host: '0.0.0.0' });
        
        console.log(`🌐 WebSocket server running on ws://0.0.0.0:${this.wsPort}`);
        
        // عرض IP للحاسوب
        const { networkInterfaces } = require('os');
        const nets = networkInterfaces();
        for (const name of Object.keys(nets)) {
            for (const net of nets[name]) {
                if (net.family === 'IPv4' && !net.internal) {
                    console.log(`   Connect from phone: ws://${net.address}:${this.wsPort}`);
                }
            }
        }
        console.log('   Waiting for browser connection...');
        
        this.wss.on('connection', (ws) => {
            console.log('✅ Browser connected to WebSocket');
            
            ws.on('message', (message) => {
                try {
                    const data = JSON.parse(message);
                    if (data.type === 'token') {
                        this.token = data.token;
                        console.log('✅ Auth token received');
                    }
                } catch (e) {}
            });
            
            ws.on('close', () => {
                console.log('⚠️ Browser disconnected');
            });
        });
    }

    startADBLogcat() {
        console.log('📡 Starting ADB logcat monitoring...');
        console.log('   Filtering for FitPro (cn.xiaofengkj.fitpro)');
        console.log('');
        
        // مراقبة logs تطبيق FitPro
        this.process = spawn('adb', ['logcat', '-s', 'ReceiveData:V', 'DefaultHomeBusiness:V']);
        
        this.process.stdout.on('data', (data) => {
            const lines = data.toString().split('\n');
            lines.forEach(line => {
                if (line.trim()) {
                    this.parseLogLine(line);
                }
            });
        });
        
        this.process.stderr.on('data', (data) => {
            const error = data.toString();
            if (!error.includes('warning') && !error.includes('Unable')) {
                console.error('ADB Error:', error);
            }
        });
        
        this.process.on('close', (code) => {
            console.log(`⚠️ ADB process closed (code: ${code}), restarting...`);
            setTimeout(() => this.startADBLogcat(), 3000);
        });
        
        console.log('✅ ADB monitoring active');
        console.log('   Waiting for data from FitPro app...');
        console.log('   Please measure heart rate or blood pressure on the FitPro app');
        console.log('');
    }

    parseLogLine(line) {
        // استخراج ضربات القلب
        const heartMatch = line.match(/heart:(\d+)/i);
        if (heartMatch) {
            const heartRate = parseInt(heartMatch[1]);
            if (heartRate !== this.lastHeartRate && heartRate >= 40 && heartRate <= 200) {
                console.log(`❤️ [${new Date().toLocaleTimeString()}] Heart Rate: ${heartRate} BPM`);
                this.lastHeartRate = heartRate;
                this.sendToBrowser({ type: 'health_data', heartRate });
                this.sendToAPI({ heart_rate: heartRate });
            }
        }
        
        // استخراج ضغط الدم
        const bpMatch = line.match(/bp:(\d+)\/(\d+)/i);
        if (bpMatch) {
            const systolic = parseInt(bpMatch[1]);
            const diastolic = parseInt(bpMatch[2]);
            if (systolic !== this.lastBP?.systolic && systolic >= 80 && systolic <= 200) {
                console.log(`🩸 [${new Date().toLocaleTimeString()}] Blood Pressure: ${systolic}/${diastolic} mmHg`);
                this.lastBP = { systolic, diastolic };
                this.sendToBrowser({ type: 'health_data', bloodPressure: { systolic, diastolic } });
                this.sendToAPI({ systolic_pressure: systolic, diastolic_pressure: diastolic });
            }
        }
        
        // عرض بيانات مفيدة للتصحيح
        if (line.includes('HR:') && !line.includes('heart:')) {
            const hrMatch = line.match(/HR:(\d+)/i);
            if (hrMatch) {
                const hr = parseInt(hrMatch[1]);
                if (hr !== this.lastHeartRate && hr >= 40 && hr <= 200) {
                    console.log(`❤️ [${new Date().toLocaleTimeString()}] HR from log: ${hr} BPM`);
                    this.lastHeartRate = hr;
                    this.sendToBrowser({ type: 'health_data', heartRate: hr });
                    this.sendToAPI({ heart_rate: hr });
                }
            }
        }
        
        // عرض أول 100 حرف من أي log جديد للتصحيح
        if (line.includes('ReceiveData') && (line.includes('heart') || line.includes('bp'))) {
            console.log('📝 Log sample:', line.substring(0, 120));
        }
    }

    sendToBrowser(data) {
        if (this.wss) {
            this.wss.clients.forEach(client => {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(JSON.stringify(data));
                }
            });
        }
    }

    async sendToAPI(data) {
        if (!this.token) {
            return;
        }
        
        try {
            const response = await axios.post(`${this.apiUrl}/api/watch/adb-data/`, 
                { ...data, recorded_at: new Date().toISOString() },
                {
                    headers: {
                        'Authorization': `Bearer ${this.token}`,
                        'Content-Type': 'application/json'
                    },
                    timeout: 5000
                }
            );
            
            if (response.data.success) {
                console.log('   ✅ Saved to database');
            }
        } catch (error) {
            if (error.code === 'ECONNREFUSED') {
                // الخادم ليس قيد التشغيل
            } else {
                console.error('   ❌ Save failed:', error.message);
            }
        }
    }

    stop() {
        console.log('');
        console.log('🛑 Stopping ADB Monitor...');
        if (this.process) {
            this.process.kill();
        }
        if (this.wss) {
            this.wss.close();
        }
        process.exit(0);
    }
}

// تشغيل المراقب
const monitor = new ADBMonitor();
monitor.start();

// التعامل مع إغلاق البرنامج
process.on('SIGINT', () => monitor.stop());
process.on('SIGTERM', () => monitor.stop());
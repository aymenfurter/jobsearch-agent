/**
 * Handles audio recording and processing using Web Audio API
 */
export class Recorder {
    onDataAvailable: (buffer: Iterable<number>) => void;
    private audioContext: AudioContext | null = null;
    private mediaStream: MediaStream | null = null;
    private mediaStreamSource: MediaStreamAudioSourceNode | null = null;
    private workletNode: AudioWorkletNode | null = null;
    private gainNode: GainNode | null = null;
    private isMuted: boolean = false;

    public constructor(onDataAvailable: (buffer: Iterable<number>) => void) {
        this.onDataAvailable = onDataAvailable;
    }

    /**
     * Initializes and starts the audio recording process
     * @param stream - Media stream from user's microphone
     */
    async start(stream: MediaStream): Promise<void> {
        try {
            if (this.audioContext) {
                await this.audioContext.close();
            }

            this.audioContext = new AudioContext({ sampleRate: 24000 });

            await this.audioContext.audioWorklet.addModule("./audio-processor-worklet.js");

            this.mediaStream = stream;
            this.mediaStreamSource = this.audioContext.createMediaStreamSource(this.mediaStream);

            this.workletNode = new AudioWorkletNode(this.audioContext, "audio-processor-worklet");
            this.workletNode.port.onmessage = event => {
                this.onDataAvailable(event.data.buffer);
            };

            this.gainNode = this.audioContext.createGain();
            this.mediaStreamSource.connect(this.gainNode);
            this.gainNode.connect(this.workletNode);
            this.workletNode.connect(this.audioContext.destination);

            // Initialize mute state
            this.setMuted(this.isMuted);
        } catch (error) {
            this.stop();
        }
    }

    setMuted(muted: boolean) {
        this.isMuted = muted;
        if (this.gainNode) {
            this.gainNode.gain.value = muted ? 0 : 1;
        }
    }

    getMuted(): boolean {
        return this.isMuted;
    }

    async stop() {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
        }

        this.mediaStreamSource = null;
        this.workletNode = null;
        this.gainNode = null;
    }
}

/**
 * Manages audio playback functionality using Web Audio API
 */
export class Player {
    private playbackNode: AudioWorkletNode | null = null;
    private audioContext: AudioContext | null = null;
    private gainNode: GainNode | null = null;
    private isMuted: boolean = false;

    /**
     * Initializes the audio context and sets up the audio processing chain
     * @param sampleRate - The sample rate for audio playback
     */
    async init(sampleRate: number): Promise<void> {
        this.audioContext = new AudioContext({ sampleRate });
        await this.audioContext.audioWorklet.addModule("audio-playback-worklet.js");

        this.playbackNode = new AudioWorkletNode(this.audioContext, "audio-playback-worklet");
        this.gainNode = this.audioContext.createGain();
        
        this.playbackNode.connect(this.gainNode);
        this.gainNode.connect(this.audioContext.destination);
    }

    /**
     * Plays the provided audio buffer
     * @param buffer - Audio data as Int16Array
     */
    play(buffer: Int16Array): void {
        if (this.playbackNode) {
            this.playbackNode.port.postMessage(buffer);
        }
    }

    stop() {
        if (this.playbackNode) {
            this.playbackNode.port.postMessage(null);
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
}

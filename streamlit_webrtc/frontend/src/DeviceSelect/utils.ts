export function stopAllTracks(stream: MediaStream) {
  stream.getVideoTracks().forEach((track) => track.stop());
  stream.getAudioTracks().forEach((track) => track.stop());
}

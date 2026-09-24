fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos") {
        // The final extension must retain Objective-C categories from static WebRTC.
        // https://github.com/livekit/rust-sdks/blob/c9445106eec8fe437d8e8d0ff4ba6158698c6bb4/README.md#macos
        println!("cargo:rustc-link-arg=-ObjC");
    }
}

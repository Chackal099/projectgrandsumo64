// Timeout callback for the synthetic harness's standalone upstream Duktape build.
// Project64 supplies its own callback; this file is never linked into an emulator.
#include <chrono>
extern "C" int DukTimeoutCheck(void*) {
    static const auto started = std::chrono::steady_clock::now();
    return std::chrono::steady_clock::now() - started > std::chrono::seconds(30);
}

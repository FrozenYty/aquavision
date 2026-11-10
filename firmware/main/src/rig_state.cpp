// Reason tokens and their mapping. In their own small unit so the parser and the renderer agree
// without including each other.

#include "rig_state.h"

namespace rig {

const char* reasonToken(Reason reason) {
  switch (reason) {
    case Reason::LowLight:
      return "LOW_LIGHT";
    case Reason::Blur:
      return "BLUR";
    case Reason::ColorCast:
      return "COLOR_CAST";
    case Reason::None:
      return "NONE";
    case Reason::NoReply:
      return "NO_REPLY";
    default:
      return "UNKNOWN";
  }
}

Reason reasonFromToken(const char* token) {
  if (token == nullptr) {
    return Reason::None;
  }
  if (strcmp(token, "LOW_LIGHT") == 0) {
    return Reason::LowLight;
  }
  if (strcmp(token, "BLUR") == 0) {
    return Reason::Blur;
  }
  if (strcmp(token, "COLOR_CAST") == 0) {
    return Reason::ColorCast;
  }
  if (strcmp(token, "NONE") == 0) {
    return Reason::None;
  }
  if (strcmp(token, "NO_REPLY") == 0) {
    return Reason::NoReply;
  }
  return Reason::Unknown;
}

}  // namespace rig

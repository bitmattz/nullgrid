# NULLGRID zsh setup: /usr/share/nullgrid/zsh/nullgrid.zsh, sourced from ~/.zshrc.
# Put your own settings in ~/.zshrc after the line that sources this file.
[[ -o interactive ]] || return

: ${XDG_CONFIG_HOME:=$HOME/.config} ${XDG_STATE_HOME:=$HOME/.local/state} ${XDG_CACHE_HOME:=$HOME/.cache}

# --- first run: default dotfiles + generated theme files --------------------
if [[ ! -e $XDG_STATE_HOME/nullgrid/initialized ]] && (( $+commands[nullgrid] )); then
  nullgrid init --quiet
fi
[[ -r $XDG_CONFIG_HOME/nullgrid/generated/shell-env.sh ]] && source $XDG_CONFIG_HOME/nullgrid/generated/shell-env.sh
: ${NULLGRID_ANSI_PRIMARY:=6} ${NULLGRID_ANSI_SECONDARY:=1} ${NULLGRID_ANSI_WARNING:=3} ${NULLGRID_ANSI_DIM:=8}

# --- Linux console: theme palette and console-safe variants of the apps ------
if [[ $TERM == linux ]]; then
  [[ -r $XDG_CONFIG_HOME/nullgrid/generated/tty-palette.sh ]] && source $XDG_CONFIG_HOME/nullgrid/generated/tty-palette.sh
  export STARSHIP_CONFIG=$XDG_CONFIG_HOME/starship-tty.toml
  export YAZI_CONFIG_HOME=$XDG_CONFIG_HOME/yazi-tty
  alias cava="cava -p $XDG_CONFIG_HOME/cava/config-tty"
else
  # inherited from a console login: not for a real terminal
  [[ $STARSHIP_CONFIG == */starship-tty.toml ]] && unset STARSHIP_CONFIG
  [[ $YAZI_CONFIG_HOME == */yazi-tty ]] && unset YAZI_CONFIG_HOME
fi

# --- environment -------------------------------------------------------------
export EDITOR=nvim VISUAL=nvim PAGER=less LESS=-R
typeset -U path
path=($HOME/.local/bin $path)

# --- history -----------------------------------------------------------------
mkdir -p $XDG_STATE_HOME/zsh $XDG_CACHE_HOME/zsh
HISTFILE=$XDG_STATE_HOME/zsh/history
HISTSIZE=50000
SAVEHIST=50000
setopt extended_history hist_ignore_dups hist_ignore_space hist_reduce_blanks share_history
setopt auto_cd interactive_comments no_beep

# --- completion --------------------------------------------------------------
autoload -Uz compinit
compinit -d $XDG_CACHE_HOME/zsh/zcompdump
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*:descriptions' format "%F{$NULLGRID_ANSI_PRIMARY}-- %d --%f"

# --- keys (emacs style, plus the usual Home/End/Delete/Ctrl-arrows) ------------
bindkey -e
bindkey '^[[H' beginning-of-line '^[[F' end-of-line '^[[1~' beginning-of-line '^[[4~' end-of-line
bindkey '^[[3~' delete-char '^[[1;5C' forward-word '^[[1;5D' backward-word

# --- aliases -------------------------------------------------------------------
alias ls='ls --color=auto --group-directories-first'
alias ll='ls -lh' la='ls -lAh'
alias grep='grep --color=auto'
alias v=nvim lg=lazygit ff=fastfetch hud=nullgrid-dash
# yazi that leaves the shell in the directory you quit in
y() {
  local tmp=$(mktemp -t yazi-cwd.XXXXXX) cwd
  yazi "$@" --cwd-file=$tmp
  cwd=$(<$tmp)
  [[ -n $cwd && $cwd != $PWD ]] && builtin cd -- $cwd
  rm -f -- $tmp
}

# --- plugins -------------------------------------------------------------------
_ng_plugins=/usr/share/zsh/plugins
if [[ -r $_ng_plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=$NULLGRID_ANSI_DIM"
  ZSH_AUTOSUGGEST_STRATEGY=(history completion)
  source $_ng_plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
fi
if [[ -r $_ng_plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source $_ng_plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
  # Palette slots, so the colors follow the theme in kitty and on the console.
  ZSH_HIGHLIGHT_STYLES[command]="fg=$NULLGRID_ANSI_PRIMARY"
  ZSH_HIGHLIGHT_STYLES[builtin]="fg=$NULLGRID_ANSI_PRIMARY"
  ZSH_HIGHLIGHT_STYLES[alias]="fg=$NULLGRID_ANSI_PRIMARY"
  ZSH_HIGHLIGHT_STYLES[function]="fg=$NULLGRID_ANSI_PRIMARY"
  ZSH_HIGHLIGHT_STYLES[precommand]="fg=$NULLGRID_ANSI_PRIMARY,underline"
  ZSH_HIGHLIGHT_STYLES[reserved-word]="fg=$NULLGRID_ANSI_SECONDARY"
  ZSH_HIGHLIGHT_STYLES[unknown-token]="fg=$NULLGRID_ANSI_SECONDARY,bold"
  ZSH_HIGHLIGHT_STYLES[path]="underline"
  ZSH_HIGHLIGHT_STYLES[single-quoted-argument]="fg=$NULLGRID_ANSI_WARNING"
  ZSH_HIGHLIGHT_STYLES[double-quoted-argument]="fg=$NULLGRID_ANSI_WARNING"
  ZSH_HIGHLIGHT_STYLES[comment]="fg=$NULLGRID_ANSI_DIM"
fi
unset _ng_plugins

# --- prompt --------------------------------------------------------------------
if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
else
  PROMPT="%F{$NULLGRID_ANSI_PRIMARY}[%n@%m]%f %F{$NULLGRID_ANSI_SECONDARY}%~%f %# "
fi

# --- sounds: a long command finished, a command failed ---------------------------
# Off by default ([sound.events] command_done / command_failed). The event goes straight to
# the nullgrid-sfx socket (zsh/net/socket): no process is started per prompt.
if [[ -n $NULLGRID_SFX_SHELL ]] && zmodload zsh/net/socket zsh/datetime 2>/dev/null; then
  _ng_sfx() {
    zsocket ${XDG_RUNTIME_DIR:-/tmp}/nullgrid-sfx.sock 2>/dev/null || return 0
    local fd=$REPLY
    print -u $fd "play $1"
    exec {fd}>&-
  }
  _ng_sfx_preexec() { _ng_sfx_start=$EPOCHREALTIME }
  _ng_sfx_precmd() {
    local st=$?
    if [[ -n $_ng_sfx_start ]]; then
      local took=$(( EPOCHREALTIME - _ng_sfx_start ))
      unset _ng_sfx_start
      # 130/148: stopped with Ctrl-C / Ctrl-Z, not a failure
      if (( st != 0 && st != 130 && st != 148 )); then
        [[ " $NULLGRID_SFX_SHELL " == *" command_failed "* ]] && _ng_sfx command_failed
      elif (( took >= 10 )); then
        [[ " $NULLGRID_SFX_SHELL " == *" command_done "* ]] && _ng_sfx command_done
      fi
    fi
    return $st  # the prompt (starship) still sees the command's status
  }
  autoload -Uz add-zsh-hook
  add-zsh-hook preexec _ng_sfx_preexec
  precmd_functions=(_ng_sfx_precmd $precmd_functions)  # first, to read the command's $?
fi

# --- login banner ----------------------------------------------------------------
if [[ -o login ]]; then
  [[ -r $XDG_CONFIG_HOME/nullgrid/generated/banner ]] && cat $XDG_CONFIG_HOME/nullgrid/generated/banner
  [[ -r /etc/nullgrid/live-hints ]] && cat /etc/nullgrid/live-hints  # only on the live ISO
fi

# --- session -------------------------------------------------------------------
# Login on tty1 starts the configured mode (nullgrid mode desktop|tty).
# Desktop mode: Hyprland (or Sway, see nullgrid-session); TTY mode or no desktop: the dashboard.
_ng_session() {
  if [[ $NULLGRID_MODE == desktop ]] && (( $+commands[nullgrid-session] )); then
    nullgrid-session
    case $? in
      0) print -P "%F{$NULLGRID_ANSI_DIM}left the desktop; run nullgrid-session to start it again%f"; return ;;
      1) print -P "%F{$NULLGRID_ANSI_WARNING}the desktop could not start; starting TTY mode. Details: nullgrid doctor%f"
         read -s -k 1 -t 10 "?press a key (or wait 10 s)" ;;
      *) print -P "%F{$NULLGRID_ANSI_WARNING}the desktop stopped with an error (logs: ~/.local/state/nullgrid/session-*.log)%f"; return ;;
    esac
  fi
  (( $+commands[nullgrid-dash] )) && nullgrid-dash
}
if [[ -o login && $TTY == /dev/tty1 && -z $WAYLAND_DISPLAY && -z $TMUX && -z $NULLGRID_NO_SESSION ]]; then
  _ng_session
fi

# A desktop terminal greets with fastfetch once (not in nested shells or tmux).
if [[ $NULLGRID_GREETING == fastfetch && $TERM == xterm-kitty && -z $TMUX && -z $NULLGRID_GREETED ]] \
    && (( $+commands[fastfetch] )); then
  export NULLGRID_GREETED=1
  fastfetch
fi

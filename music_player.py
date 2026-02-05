import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import pygame
import os
from pathlib import Path
from mutagen import File as MutagenFile
import threading
import time
import re

try:
    import vlc  # type: ignore
except Exception:
    vlc = None

class HoverButton(tk.Button):
    """Custom button class with hover effects"""
    def __init__(self, master, hover_color=None, **kwargs):
        self.default_bg = kwargs.get('bg', '#4a4a4a')
        self.hover_bg = hover_color if hover_color else self.lighten_color(self.default_bg)
        self.active_bg = kwargs.get('activebackground', self.hover_bg)
        
        kwargs['relief'] = kwargs.get('relief', tk.FLAT)
        kwargs['bd'] = kwargs.get('bd', 0)
        kwargs['cursor'] = kwargs.get('cursor', 'hand2')
        kwargs['font'] = kwargs.get('font', ('Segoe UI', 10))
        
        super().__init__(master, **kwargs)
        
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_click)
        self.bind('<ButtonRelease-1>', self.on_release)
    
    def on_enter(self, event):
        self.config(bg=self.hover_bg)
    
    def on_leave(self, event):
        self.config(bg=self.default_bg)
    
    def on_click(self, event):
        self.config(relief=tk.SUNKEN)
    
    def on_release(self, event):
        self.config(relief=tk.FLAT)
        self.config(bg=self.hover_bg)
    
    def lighten_color(self, color):
        """Lighten a hex color"""
        if color.startswith('#'):
            rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            rgb = tuple(min(255, c + 30) for c in rgb)
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        return color

class PlaylistItem(tk.Frame):
    """Custom playlist item widget with icon and name"""
    def __init__(self, master, playlist_name, icon, is_selected=False, command=None, **kwargs):
        # Extract bg from kwargs to avoid passing it twice
        bg_color = kwargs.pop('bg', '#1a1a1a')
        super().__init__(master, bg=bg_color, **kwargs)
        
        self.playlist_name = playlist_name
        self.icon = icon
        self.is_selected = is_selected
        self.command = command
        
        self.bg_color = bg_color
        self.hover_color = '#2a2a2a'
        self.selected_color = '#333333'
        
        self.create_widgets()
        self.bind_events()
    
    def create_widgets(self):
        # Icon label
        self.icon_label = tk.Label(
            self,
            text=self.icon,
            font=("Segoe UI", 16),
            bg=self.bg_color,
            fg="#ffffff"
        )
        self.icon_label.pack(side=tk.LEFT, padx=(15, 10), pady=12)
        
        # Name label
        self.name_label = tk.Label(
            self,
            text=self.playlist_name,
            font=("Segoe UI", 13),
            bg=self.bg_color,
            fg="#ffffff",
            anchor='w'
        )
        self.name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        
        if self.is_selected:
            self.select()
    
    def bind_events(self):
        for widget in [self, self.icon_label, self.name_label]:
            widget.bind('<Enter>', self.on_enter)
            widget.bind('<Leave>', self.on_leave)
            widget.bind('<Button-1>', self.on_click)
            widget.config(cursor='hand2')
    
    def on_enter(self, event):
        if not self.is_selected:
            self.config(bg=self.hover_color)
            self.icon_label.config(bg=self.hover_color)
            self.name_label.config(bg=self.hover_color)
    
    def on_leave(self, event):
        if not self.is_selected:
            self.config(bg=self.bg_color)
            self.icon_label.config(bg=self.bg_color)
            self.name_label.config(bg=self.bg_color)
    
    def on_click(self, event):
        if self.command:
            self.command()
    
    def select(self):
        self.is_selected = True
        self.config(bg=self.selected_color)
        self.icon_label.config(bg=self.selected_color)
        self.name_label.config(bg=self.selected_color)
    
    def deselect(self):
        self.is_selected = False
        self.config(bg=self.bg_color)
        self.icon_label.config(bg=self.bg_color)
        self.name_label.config(bg=self.bg_color)

class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("1200x800")
        self.root.configure(bg="#0f0f0f")
        self.root.resizable(True, True)
        
        # Color scheme
        self.colors = {
            'bg': '#0f0f0f',
            'bg_secondary': '#1a1a1a',
            'bg_tertiary': '#252525',
            'sidebar': '#121212',
            'accent': '#1DB954',
            'accent_hover': '#1ed760',
            'text': '#ffffff',
            'text_secondary': '#b3b3b3',
            'progress': '#1DB954',
            'progress_bg': '#333333',
            'selected': '#2a2a2a'
        }
        
        # Audio backend: prefer VLC (better codec support on Windows), fallback to pygame
        self._use_vlc = vlc is not None
        self._vlc_instance = None
        self._vlc_player = None

        if self._use_vlc:
            try:
                self._vlc_instance = vlc.Instance()
                self._vlc_player = self._vlc_instance.media_player_new()
            except Exception:
                self._use_vlc = False
                self._vlc_instance = None
                self._vlc_player = None

        # Initialize pygame mixer with proper settings (fallback backend)
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            # If pygame fails but VLC exists, we can still run
            if not self._use_vlc:
                try:
                    pygame.mixer.init()
                except Exception as e2:
                    messagebox.showerror(
                        "Initialization Error",
                        f"Failed to initialize audio system:\n{str(e2)}\n\n"
                        "Please make sure your audio drivers are installed and working."
                    )
        
        # Player state
        self.all_songs = []  # All songs in library
        self.favourites = []  # Favourite songs
        self.playlists = {}  # Custom playlists: {name: [file_paths]}
        self.current_playlist_name = "All"  # Currently selected playlist
        self.current_playlist = []  # Songs in current playlist view (starts as all_songs)
        self.current_index = 0
        self.is_playing = False
        self.is_paused = False
        self.volume = 0.7
        self._backend_set_volume(self.volume)
        
        # Initialize default playlists
        self.playlists["All"] = []
        self.playlists["Favourite"] = []
        
        # Configure styles
        self.configure_styles()
        
        # Create GUI
        self.create_widgets()
        
        # Auto-load songs from "songs" folder if it exists
        self.auto_load_songs_folder()
        
        # Initialize current playlist to "All"
        self.current_playlist = self.all_songs.copy()
        self.update_song_list_display()
        
        # Start progress update thread
        self.update_progress()
    
    def configure_styles(self):
        """Configure ttk styles for professional look"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Progress bar style
        style.configure(
            "Custom.Horizontal.TProgressbar",
            background=self.colors['progress'],
            troughcolor=self.colors['progress_bg'],
            borderwidth=0,
            lightcolor=self.colors['progress'],
            darkcolor=self.colors['progress'],
            thickness=6
        )
        
        # Volume slider style
        style.configure(
            "Custom.Horizontal.TScale",
            background=self.colors['bg'],
            troughcolor=self.colors['progress_bg'],
            borderwidth=0,
            sliderthickness=12,
            sliderrelief=tk.FLAT
        )
        style.map(
            "Custom.Horizontal.TScale",
            background=[('active', self.colors['accent'])],
            slidercolor=[('active', self.colors['accent'])]
        )
    
    def create_widgets(self):
        # Main container (horizontal layout)
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left sidebar for playlists
        self.create_sidebar(main_container)
        
        # Right side - main content area
        right_container = tk.Frame(main_container, bg=self.colors['bg'])
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Top section - song list
        self.create_song_list(right_container)
        
        # Bottom section - player controls (fixed at bottom)
        self.create_player_controls(right_container)
    
    def create_sidebar(self, parent):
        """Create left sidebar with playlists"""
        sidebar = tk.Frame(parent, bg=self.colors['sidebar'], width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Logo/Title
        title_frame = tk.Frame(sidebar, bg=self.colors['sidebar'])
        title_frame.pack(fill=tk.X, pady=(20, 30))
        
        title_label = tk.Label(
            title_frame,
            text="🎵 Music Player",
            font=("Segoe UI", 20, "bold"),
            bg=self.colors['sidebar'],
            fg=self.colors['text']
        )
        title_label.pack()
        
        # Create playlist button
        create_btn = HoverButton(
            sidebar,
            text="➕ Create Playlist",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors['accent'],
            fg="#ffffff",
            hover_color=self.colors['accent_hover'],
            activebackground=self.colors['accent_hover'],
            activeforeground="#ffffff",
            padx=15,
            pady=10,
            command=self.create_playlist
        )
        create_btn.pack(fill=tk.X, padx=15, pady=(0, 20))
        
        # Playlists container with scrollbar
        playlists_frame = tk.Frame(sidebar, bg=self.colors['sidebar'])
        playlists_frame.pack(fill=tk.BOTH, expand=True, padx=0)
        
        # Canvas for scrolling
        canvas = tk.Canvas(playlists_frame, bg=self.colors['sidebar'], highlightthickness=0)
        scrollbar = tk.Scrollbar(playlists_frame, orient="vertical", command=canvas.yview, bg=self.colors['sidebar'])
        scrollable_frame = tk.Frame(canvas, bg=self.colors['sidebar'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.playlists_container = scrollable_frame
        self.playlists_canvas = canvas
        
        # Store playlist items
        self.playlist_items = {}
        
        # Bind right-click on playlist items
        self.playlists_container.bind('<Button-3>', self.show_playlist_context_menu)
        
        # Add default playlists
        self.add_playlist_item("All", "📀", True)
        self.add_playlist_item("Favourite", "❤️", False)
        
        # File operations at bottom of sidebar
        file_ops_frame = tk.Frame(sidebar, bg=self.colors['sidebar'])
        file_ops_frame.pack(fill=tk.X, padx=15, pady=15)
        
        add_file_btn = HoverButton(
            file_ops_frame,
            text="➕ Add File",
            font=("Segoe UI", 10),
            bg="#2196F3",
            fg="#ffffff",
            hover_color="#42a5f5",
            activebackground="#1976d2",
            activeforeground="#ffffff",
            padx=10,
            pady=8,
            command=self.add_file
        )
        add_file_btn.pack(fill=tk.X, pady=(0, 8))
        
        add_folder_btn = HoverButton(
            file_ops_frame,
            text="📁 Add Folder",
            font=("Segoe UI", 10),
            bg="#2196F3",
            fg="#ffffff",
            hover_color="#42a5f5",
            activebackground="#1976d2",
            activeforeground="#ffffff",
            padx=10,
            pady=8,
            command=self.add_folder
        )
        add_folder_btn.pack(fill=tk.X)
    
    def add_playlist_item(self, name, icon, is_selected=False):
        """Add a playlist item to the sidebar"""
        item = PlaylistItem(
            self.playlists_container,
            name,
            icon,
            is_selected=is_selected,
            command=lambda: self.select_playlist(name),
            bg=self.colors['sidebar']
        )
        item.pack(fill=tk.X, padx=0, pady=2)
        self.playlist_items[name] = item
        
        # Bind right-click to item
        for widget in [item, item.icon_label, item.name_label]:
            widget.bind('<Button-3>', lambda e, n=name: self.show_playlist_context_menu(e, n))
        
        # Update canvas scroll region
        self.playlists_canvas.update_idletasks()
        self.playlists_canvas.configure(scrollregion=self.playlists_canvas.bbox("all"))
    
    def select_playlist(self, playlist_name):
        """Select a playlist and display its songs"""
        # Deselect all
        for item in self.playlist_items.values():
            item.deselect()
        
        # Select clicked playlist
        if playlist_name in self.playlist_items:
            self.playlist_items[playlist_name].select()
        
        # Update current playlist
        self.current_playlist_name = playlist_name
        if playlist_name == "All":
            self.current_playlist = self.all_songs.copy()
        elif playlist_name == "Favourite":
            self.current_playlist = self.favourites.copy()
        else:
            self.current_playlist = self.playlists.get(playlist_name, []).copy()
        
        # Update song list display
        self.update_song_list_display()
    
    def create_song_list(self, parent):
        """Create main song list area"""
        # Header
        header_frame = tk.Frame(parent, bg=self.colors['bg'])
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        playlist_title = tk.Label(
            header_frame,
            text="All Songs",
            font=("Segoe UI", 24, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        playlist_title.pack(side=tk.LEFT)
        self.playlist_title_label = playlist_title
        
        song_count_label = tk.Label(
            header_frame,
            text="(0 songs)",
            font=("Segoe UI", 12),
            bg=self.colors['bg'],
            fg=self.colors['text_secondary']
        )
        song_count_label.pack(side=tk.LEFT, padx=(15, 0))
        self.song_count_label = song_count_label
        
        # Song list container
        list_container = tk.Frame(parent, bg=self.colors['bg_secondary'])
        list_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Scrollbar
        scrollbar = tk.Scrollbar(list_container, bg=self.colors['bg_tertiary'], troughcolor=self.colors['bg_secondary'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.song_listbox = tk.Listbox(
            list_container,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text'],
            selectbackground=self.colors['accent'],
            selectforeground="#ffffff",
            font=("Segoe UI", 12),
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            activestyle='none'
        )
        self.song_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        scrollbar.config(command=self.song_listbox.yview)
        
        # Bind events
        self.song_listbox.bind('<Double-1>', self.on_song_select)
        self.song_listbox.bind('<Button-3>', self.show_song_context_menu)  # Right-click
        self.song_listbox.bind('<Enter>', lambda e: self.song_listbox.config(cursor='hand2'))
        self.song_listbox.bind('<Leave>', lambda e: self.song_listbox.config(cursor=''))
    
    def create_player_controls(self, parent):
        """Create bottom player controls"""
        # Player container (fixed at bottom)
        player_frame = tk.Frame(parent, bg=self.colors['bg_secondary'], height=180)
        player_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
        player_frame.pack_propagate(False)
        
        # Current song info
        song_info_frame = tk.Frame(player_frame, bg=self.colors['bg_secondary'])
        song_info_frame.pack(fill=tk.X, padx=30, pady=(20, 10))
        
        self.current_song_label = tk.Label(
            song_info_frame,
            text="No song selected",
            font=("Segoe UI", 14, "bold"),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text'],
            wraplength=1000,
            justify=tk.CENTER,
            anchor=tk.CENTER
        )
        self.current_song_label.pack(fill=tk.X)
        
        # Progress bar frame
        progress_frame = tk.Frame(player_frame, bg=self.colors['bg_secondary'])
        progress_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
        
        progress_container = tk.Frame(progress_frame, bg=self.colors['bg_secondary'])
        progress_container.pack(fill=tk.X)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_container,
            variable=self.progress_var,
            maximum=100,
            mode='determinate',
            style="Custom.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        
        self.time_label = tk.Label(
            progress_container,
            text="00:00 / 00:00",
            font=("Segoe UI", 10),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary'],
            width=12
        )
        self.time_label.pack(side=tk.RIGHT)
        
        # Control buttons (centered)
        control_frame = tk.Frame(player_frame, bg=self.colors['bg_secondary'])
        control_frame.pack(pady=(0, 15))
        
        # Previous button
        prev_btn = HoverButton(
            control_frame,
            text="⏮",
            font=("Segoe UI", 18),
            bg=self.colors['bg_tertiary'],
            fg=self.colors['text'],
            hover_color='#353535',
            activebackground='#404040',
            activeforeground=self.colors['text'],
            padx=18,
            pady=10,
            command=self.previous_song
        )
        prev_btn.pack(side=tk.LEFT, padx=8)
        
        # Play/Pause button
        self.play_btn = HoverButton(
            control_frame,
            text="▶",
            font=("Segoe UI", 28, "bold"),
            bg=self.colors['accent'],
            fg="#ffffff",
            hover_color=self.colors['accent_hover'],
            activebackground=self.colors['accent_hover'],
            activeforeground="#ffffff",
            padx=25,
            pady=12,
            command=self.toggle_play_pause
        )
        self.play_btn.pack(side=tk.LEFT, padx=8)
        
        # Stop button
        stop_btn = HoverButton(
            control_frame,
            text="⏹",
            font=("Segoe UI", 18),
            bg=self.colors['bg_tertiary'],
            fg=self.colors['text'],
            hover_color='#353535',
            activebackground='#404040',
            activeforeground=self.colors['text'],
            padx=18,
            pady=10,
            command=self.stop_song
        )
        stop_btn.pack(side=tk.LEFT, padx=8)
        
        # Next button
        next_btn = HoverButton(
            control_frame,
            text="⏭",
            font=("Segoe UI", 18),
            bg=self.colors['bg_tertiary'],
            fg=self.colors['text'],
            hover_color='#353535',
            activebackground='#404040',
            activeforeground=self.colors['text'],
            padx=18,
            pady=10,
            command=self.next_song
        )
        next_btn.pack(side=tk.LEFT, padx=8)
        
        # Volume control (right side)
        volume_frame = tk.Frame(player_frame, bg=self.colors['bg_secondary'])
        volume_frame.pack(side=tk.RIGHT, padx=30, pady=(0, 15))
        
        volume_label = tk.Label(
            volume_frame,
            text="🔊",
            font=("Segoe UI", 14),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary']
        )
        volume_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.volume_var = tk.DoubleVar(value=self.volume * 100)
        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            variable=self.volume_var,
            orient=tk.HORIZONTAL,
            length=120,
            style="Custom.Horizontal.TScale",
            command=self.set_volume
        )
        self.volume_scale.pack(side=tk.LEFT, padx=(0, 10))
        
        self.volume_value_label = tk.Label(
            volume_frame,
            text=f"{int(self.volume * 100)}%",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text'],
            width=4
        )
        self.volume_value_label.pack(side=tk.LEFT)
    
    def create_playlist(self):
        """Create a new playlist"""
        name = simpledialog.askstring("Create Playlist", "Enter playlist name:")
        if name and name.strip():
            name = name.strip()
            if name in self.playlists:
                messagebox.showwarning("Warning", f"Playlist '{name}' already exists!")
                return
            
            self.playlists[name] = []
            self.add_playlist_item(name, "📋", False)
            messagebox.showinfo("Success", f"Playlist '{name}' created!")
    
    def add_file(self):
        """Add a single audio file to library"""
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("MP3 Files", "*.mp3"),
                ("WAV Files", "*.wav"),
                ("OGG Files", "*.ogg"),
                ("FLAC Files", "*.flac"),
                ("M4A Files", "*.m4a"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            if file_path not in self.all_songs:
                self.all_songs.append(file_path)
                self.playlists["All"].append(file_path)
                
                # Update display if "All" is selected
                if self.current_playlist_name == "All":
                    self.current_playlist.append(file_path)
                    self.update_song_list_display()
                
                self.update_song_count()
    
    def auto_load_songs_folder(self):
        """Automatically load songs from 'songs' folder in the application directory"""
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        songs_folder = os.path.join(script_dir, "songs")
        
        # Check if songs folder exists
        if os.path.exists(songs_folder) and os.path.isdir(songs_folder):
            audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
            added_count = 0
            
            # Scan the songs folder recursively
            for root, dirs, files in os.walk(songs_folder):
                for file in files:
                    if Path(file).suffix.lower() in audio_extensions:
                        file_path = os.path.join(root, file)
                        if file_path not in self.all_songs:
                            self.all_songs.append(file_path)
                            self.playlists["All"].append(file_path)
                            added_count += 1
            
            # Update display if songs were found
            if added_count > 0:
                if self.current_playlist_name == "All":
                    self.current_playlist = self.all_songs.copy()
                    self.update_song_list_display()
                self.update_song_count()
                print(f"Auto-loaded {added_count} song(s) from 'songs' folder")
    
    def add_folder(self):
        """Add all audio files from a folder to library"""
        folder_path = filedialog.askdirectory(title="Select Folder")
        if folder_path:
            audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
            added_count = 0
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if Path(file).suffix.lower() in audio_extensions:
                        file_path = os.path.join(root, file)
                        if file_path not in self.all_songs:
                            self.all_songs.append(file_path)
                            self.playlists["All"].append(file_path)
                            added_count += 1
            
            if added_count > 0:
                # Update display if "All" is selected
                if self.current_playlist_name == "All":
                    self.current_playlist = self.all_songs.copy()
                    self.update_song_list_display()
                
                self.update_song_count()
                messagebox.showinfo("Success", f"Added {added_count} song(s) to library")
            else:
                messagebox.showwarning("Warning", "No audio files found in the selected folder")
    
    def update_song_list_display(self):
        """Update the song list display"""
        self.song_listbox.delete(0, tk.END)
        for file_path in self.current_playlist:
            song_info = self.get_song_info(file_path)
            self.song_listbox.insert(tk.END, song_info)
        
        # Update title and count
        self.playlist_title_label.config(text=self.current_playlist_name)
        self.update_song_count()
    
    def update_song_count(self):
        """Update song count label"""
        count = len(self.current_playlist)
        if count == 1:
            self.song_count_label.config(text=f"({count} song)")
        else:
            self.song_count_label.config(text=f"({count} songs)")
    
    def on_song_select(self, event):
        """Handle double-click on song"""
        selection = self.song_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            self.play_song()
    
    def get_song_info(self, file_path):
        """Extract song title only (no artist) from metadata or filename"""
        try:
            audio_file = MutagenFile(file_path)
            if audio_file is not None:
                title = None
                
                # Try different tag formats for title
                # MP3 tags (ID3v2)
                if 'TIT2' in audio_file:
                    title = str(audio_file['TIT2'][0]).strip()
                elif 'TITLE' in audio_file:
                    title = str(audio_file['TITLE'][0]).strip()
                elif hasattr(audio_file, 'get'):
                    if audio_file.get('TITLE'):
                        title = str(audio_file.get('TITLE')[0]).strip()
                    elif audio_file.get('TIT2'):
                        title = str(audio_file.get('TIT2')[0]).strip()
                
                # If we found a title, return it
                if title and title != 'Unknown' and title != '':
                    return title
        except Exception:
            pass
        
        # Fallback: extract song name from filename
        filename = os.path.basename(file_path)
        # Remove extension
        song_name = os.path.splitext(filename)[0]
        
        # Clean up common patterns: "Artist - Title" -> "Title"
        # Remove common separators and artist patterns
        separators = [' - ', ' – ', ' — ', '-', '_']
        for sep in separators:
            if sep in song_name:
                parts = song_name.split(sep)
                # Usually the last part is the title, but check if it's longer
                if len(parts) > 1:
                    # Take the last part as title (most common format)
                    song_name = parts[-1].strip()
                    break
        
        # Remove common prefixes like track numbers "01. Song Name" -> "Song Name"
        import re
        song_name = re.sub(r'^\d+[.\s\-_]+', '', song_name, count=1)
        song_name = song_name.strip()
        
        return song_name if song_name else "Unknown Song"
    
    def play_song(self):
        """Play the current song"""
        if not self.current_playlist:
            messagebox.showwarning("Warning", "Playlist is empty!")
            return
        
        if self.current_index >= len(self.current_playlist):
            self.current_index = 0
        
        try:
            file_path = self.current_playlist[self.current_index]
            
            # Check if file exists
            if not os.path.exists(file_path):
                messagebox.showerror("Error", f"File not found:\n{file_path}")
                return

            # Play via backend (VLC preferred; pygame fallback)
            try:
                self._backend_stop()
                self._backend_play(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not play song:\n{str(e)}")
                return

            self.is_playing = True
            self.is_paused = False
            self.play_btn.config(text="⏸")
            
            # Update current song label
            song_info = self.get_song_info(file_path)
            if not song_info or song_info.strip() == "":
                song_info = os.path.basename(file_path)
            
            # Ensure we have a valid song name
            if not song_info:
                song_info = "Unknown Song"
            
            # Update label with proper text
            self.current_song_label.config(text=song_info)
            # Force immediate GUI update
            self.current_song_label.update_idletasks()
            self.root.update_idletasks()
            
            # Highlight current song in list
            self.song_listbox.selection_clear(0, tk.END)
            self.song_listbox.selection_set(self.current_index)
            self.song_listbox.see(self.current_index)
            
            # Check for end of song
            self.check_song_end()
            
        except Exception as e:
            error_msg = f"Could not play song: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.is_playing = False
            import traceback
            print(f"Full error traceback:\n{traceback.format_exc()}")
    
    def check_song_end(self):
        """Check if song has ended and play next"""
        if self.is_playing and not pygame.mixer.music.get_busy():
            self.next_song()
        else:
            self.root.after(1000, self.check_song_end)
    
    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if not self.current_playlist:
            messagebox.showwarning("Warning", "Playlist is empty!")
            return
        
        if not self.is_playing:
            if self.is_paused:
                self._backend_unpause()
                self.is_playing = True
                self.is_paused = False
                self.play_btn.config(text="⏸")
            else:
                self.play_song()
        else:
            self._backend_pause()
            self.is_playing = False
            self.is_paused = True
            self.play_btn.config(text="▶")
    
    def stop_song(self):
        """Stop the current song"""
        self._backend_stop()
        self.is_playing = False
        self.is_paused = False
        self.play_btn.config(text="▶")
        self.progress_var.set(0)
        self.time_label.config(text="00:00 / 00:00")
    
    def next_song(self):
        """Play next song in playlist"""
        if not self.current_playlist:
            return
        
        self.current_index = (self.current_index + 1) % len(self.current_playlist)
        self.play_song()
    
    def previous_song(self):
        """Play previous song in playlist"""
        if not self.current_playlist:
            return
        
        self.current_index = (self.current_index - 1) % len(self.current_playlist)
        self.play_song()
    
    def set_volume(self, value):
        """Set volume level"""
        self.volume = float(value) / 100.0
        self._backend_set_volume(self.volume)
        self.volume_value_label.config(text=f"{int(self.volume * 100)}%")
    
    def update_progress(self):
        """Update progress bar and time display"""
        if self.is_playing and self._backend_is_busy():
            try:
                current_pos = self._backend_get_pos_seconds()
                duration = self._backend_get_duration_seconds()
                if duration and duration > 0:
                    progress = (current_pos / duration) * 100
                    self.progress_var.set(min(progress, 100))

                    current_time = self.format_time(current_pos)
                    total_time = self.format_time(duration)
                    self.time_label.config(text=f"{current_time} / {total_time}")
            except:
                pass
        
        self.root.after(100, self.update_progress)
    
    def format_time(self, seconds):
        """Format seconds to MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    # -----------------------
    # Audio backend (VLC/pygame)
    # -----------------------
    def _backend_play(self, file_path: str) -> None:
        file_path = os.path.normpath(file_path)

        if self._use_vlc and self._vlc_instance and self._vlc_player:
            media = self._vlc_instance.media_new(file_path)
            self._vlc_player.set_media(media)
            self._vlc_player.play()
            return

        # pygame fallback
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        except pygame.error as e:
            msg = str(e)
            # This is the common Windows codec failure case you reported
            if "ModPlug_load failed" in msg:
                raise Exception(
                    "Pygame couldn't decode this file (ModPlug_load failed).\n\n"
                    "Fix: install VLC backend:\n"
                    "  pip install python-vlc\n"
                    "and install VLC player on Windows.\n\n"
                    f"Original error: {msg}"
                )
            raise

    def _backend_pause(self) -> None:
        if self._use_vlc and self._vlc_player:
            self._vlc_player.pause()
            return
        pygame.mixer.music.pause()

    def _backend_unpause(self) -> None:
        if self._use_vlc and self._vlc_player:
            # VLC pause toggles; if paused, calling pause resumes
            self._vlc_player.pause()
            return
        pygame.mixer.music.unpause()

    def _backend_stop(self) -> None:
        if self._use_vlc and self._vlc_player:
            self._vlc_player.stop()
            return
        pygame.mixer.music.stop()

    def _backend_is_busy(self) -> bool:
        if self._use_vlc and self._vlc_player:
            try:
                # VLC: 1=playing, 0=stopped, 2=paused
                return self._vlc_player.is_playing() == 1
            except Exception:
                return False
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False

    def _backend_set_volume(self, volume_0_to_1: float) -> None:
        volume_0_to_1 = max(0.0, min(1.0, float(volume_0_to_1)))
        if self._use_vlc and self._vlc_player:
            # VLC volume is 0..100
            self._vlc_player.audio_set_volume(int(volume_0_to_1 * 100))
            return
        try:
            pygame.mixer.music.set_volume(volume_0_to_1)
        except Exception:
            pass

    def _backend_get_pos_seconds(self) -> float:
        if self._use_vlc and self._vlc_player:
            ms = self._vlc_player.get_time()
            return max(0.0, ms / 1000.0) if ms and ms > 0 else 0.0
        ms = pygame.mixer.music.get_pos()
        return max(0.0, ms / 1000.0) if ms and ms > 0 else 0.0

    def _backend_get_duration_seconds(self) -> float:
        if self._use_vlc and self._vlc_player:
            ms = self._vlc_player.get_length()
            return max(0.0, ms / 1000.0) if ms and ms > 0 else 0.0

        # pygame doesn't reliably provide duration; use mutagen as fallback
        try:
            if self.current_index < len(self.current_playlist):
                file_path = self.current_playlist[self.current_index]
                audio_file = MutagenFile(file_path)
                if audio_file is not None and getattr(audio_file, "info", None):
                    return float(audio_file.info.length)
        except Exception:
            pass
        return 0.0
    
    def show_song_context_menu(self, event):
        """Show context menu for song list"""
        selection = self.song_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index >= len(self.current_playlist):
            return
        
        file_path = self.current_playlist[index]
        
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors['bg_tertiary'], fg=self.colors['text'],
                      activebackground=self.colors['accent'], activeforeground="#ffffff",
                      font=("Segoe UI", 10))
        
        # Add to Favourite
        if file_path not in self.favourites:
            menu.add_command(label="❤️ Add to Favourites", command=lambda: self.add_to_favourites(file_path))
        else:
            menu.add_command(label="💔 Remove from Favourites", command=lambda: self.remove_from_favourites(file_path))
        
        menu.add_separator()
        
        # Add to playlist submenu
        playlist_menu = tk.Menu(menu, tearoff=0, bg=self.colors['bg_tertiary'], fg=self.colors['text'],
                               activebackground=self.colors['accent'], activeforeground="#ffffff",
                               font=("Segoe UI", 10))
        
        for playlist_name in self.playlists.keys():
            if playlist_name not in ["All", "Favourite"]:
                if file_path not in self.playlists[playlist_name]:
                    playlist_menu.add_command(
                        label=playlist_name,
                        command=lambda pn=playlist_name: self.add_song_to_playlist(file_path, pn)
                    )
                else:
                    playlist_menu.add_command(
                        label=f"{playlist_name} (✓)",
                        command=lambda pn=playlist_name: self.remove_song_from_playlist(file_path, pn)
                    )
        
        if len([p for p in self.playlists.keys() if p not in ["All", "Favourite"]]) > 0:
            menu.add_cascade(label="📋 Add to Playlist", menu=playlist_menu)
        
        # Remove from current playlist (if not "All")
        if self.current_playlist_name not in ["All"]:
            menu.add_separator()
            menu.add_command(
                label="➖ Remove from Playlist",
                command=lambda: self.remove_song_from_current_playlist(index)
            )
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def show_playlist_context_menu(self, event, playlist_name=None):
        """Show context menu for playlist item"""
        if playlist_name is None:
            # Find which playlist was clicked
            y = event.y_root - self.playlists_canvas.winfo_rooty()
            for name, item in self.playlist_items.items():
                if name in ["All"]:  # Can't delete default playlists
                    continue
                try:
                    item_y = item.winfo_rooty() - self.playlists_canvas.winfo_rooty()
                    if 0 <= y - item_y <= item.winfo_height():
                        playlist_name = name
                        break
                except:
                    continue
        
        if not playlist_name or playlist_name in ["All", "Favourite"]:
            return
        
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors['bg_tertiary'], fg=self.colors['text'],
                      activebackground="#f44336", activeforeground="#ffffff",
                      font=("Segoe UI", 10))
        
        menu.add_command(
            label=f"🗑️ Delete Playlist '{playlist_name}'",
            command=lambda: self.delete_playlist(playlist_name)
        )
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def add_to_favourites(self, file_path):
        """Add song to favourites"""
        if file_path not in self.favourites:
            self.favourites.append(file_path)
            self.playlists["Favourite"].append(file_path)
            if self.current_playlist_name == "Favourite":
                self.current_playlist.append(file_path)
                self.update_song_list_display()
            messagebox.showinfo("Success", "Added to Favourites!")
    
    def remove_from_favourites(self, file_path):
        """Remove song from favourites"""
        if file_path in self.favourites:
            self.favourites.remove(file_path)
            self.playlists["Favourite"].remove(file_path)
            if self.current_playlist_name == "Favourite":
                self.current_playlist.remove(file_path)
                self.update_song_list_display()
            messagebox.showinfo("Success", "Removed from Favourites!")
    
    def add_song_to_playlist(self, file_path, playlist_name):
        """Add song to a playlist"""
        if playlist_name in self.playlists:
            if file_path not in self.playlists[playlist_name]:
                self.playlists[playlist_name].append(file_path)
                if self.current_playlist_name == playlist_name:
                    self.current_playlist.append(file_path)
                    self.update_song_list_display()
                messagebox.showinfo("Success", f"Added to '{playlist_name}'!")
    
    def remove_song_from_playlist(self, file_path, playlist_name):
        """Remove song from a playlist"""
        if playlist_name in self.playlists and file_path in self.playlists[playlist_name]:
            self.playlists[playlist_name].remove(file_path)
            if self.current_playlist_name == playlist_name:
                self.current_playlist.remove(file_path)
                self.update_song_list_display()
            messagebox.showinfo("Success", f"Removed from '{playlist_name}'!")
    
    def remove_song_from_current_playlist(self, index):
        """Remove song from current playlist"""
        if index < len(self.current_playlist):
            file_path = self.current_playlist[index]
            playlist_name = self.current_playlist_name
            
            if playlist_name in self.playlists and file_path in self.playlists[playlist_name]:
                self.playlists[playlist_name].remove(file_path)
                self.current_playlist.remove(file_path)
                self.update_song_list_display()
                
                # Update current index if needed
                if index <= self.current_index and self.current_index > 0:
                    self.current_index -= 1
                
                messagebox.showinfo("Success", "Removed from playlist!")
    
    def delete_playlist(self, playlist_name):
        """Delete a playlist"""
        if playlist_name in ["All", "Favourite"]:
            messagebox.showwarning("Warning", "Cannot delete default playlists!")
            return
        
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete '{playlist_name}'?"):
            # Remove playlist
            del self.playlists[playlist_name]
            
            # Remove from sidebar
            if playlist_name in self.playlist_items:
                self.playlist_items[playlist_name].destroy()
                del self.playlist_items[playlist_name]
            
            # If this was the current playlist, switch to "All"
            if self.current_playlist_name == playlist_name:
                self.select_playlist("All")
            
            messagebox.showinfo("Success", f"Playlist '{playlist_name}' deleted!")


def main():
    root = tk.Tk()
    app = MusicPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    main()

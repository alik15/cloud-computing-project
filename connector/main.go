package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

// ── DB ────────────────────────────────────────────────────────────────────────

func dsn() string {
	return fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_USER", "appuser"),
		getEnv("DB_PASSWORD", "apppassword"),
		getEnv("DB_NAME", "appdb"),
	)
}

func connectWithRetry() *sql.DB {
	for i := 0; i < 10; i++ {
		db, err := sql.Open("postgres", dsn())
		if err == nil {
			if err = db.Ping(); err == nil {
				log.Println("Connected to PostgreSQL")
				return db
			}
		}
		log.Printf("DB not ready, retrying in 3s... (%d/10)", i+1)
		time.Sleep(3 * time.Second)
	}
	log.Fatal("Could not connect to DB")
	return nil
}

func initSchema(db *sql.DB) {
	_, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS movies (
			id            SERIAL PRIMARY KEY,
			imdb_id       TEXT,
			title         TEXT        NOT NULL,
			year          TEXT,
			genre         TEXT,
			director      TEXT,
			poster_url    TEXT,
			imdb_rating   TEXT,
			my_rating     INTEGER CHECK (my_rating BETWEEN 1 AND 10),
			review        TEXT,
			vibes         TEXT,
			watched       BOOLEAN     NOT NULL DEFAULT FALSE,
			watched_on    DATE,
			added_on      TIMESTAMPTZ NOT NULL DEFAULT NOW()
		)
	`)
	if err != nil {
		log.Fatalf("Schema init failed: %v", err)
	}
	log.Println("Schema ready")
}

// ── Models ────────────────────────────────────────────────────────────────────

type Movie struct {
	ID         int    `json:"id"`
	ImdbID     string `json:"imdb_id"`
	Title      string `json:"title"`
	Year       string `json:"year"`
	Genre      string `json:"genre"`
	Director   string `json:"director"`
	PosterURL  string `json:"poster_url"`
	ImdbRating string `json:"imdb_rating"`
	MyRating   *int   `json:"my_rating"`
	Review     string `json:"review"`
	Vibes      string `json:"vibes"`
	Watched    bool   `json:"watched"`
	WatchedOn  string `json:"watched_on"`
	AddedOn    string `json:"added_on"`
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── OMDB proxy ────────────────────────────────────────────────────────────────

func omdbSearch(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	if query == "" {
		writeErr(w, http.StatusBadRequest, "q param required")
		return
	}
	apiKey := getEnv("OMDB_API_KEY", "")
	if apiKey == "" {
		writeErr(w, http.StatusServiceUnavailable, "OMDB_API_KEY not configured")
		return
	}
	resp, err := http.Get(fmt.Sprintf(
		"https://www.omdbapi.com/?s=%s&type=movie&apikey=%s",
		url.QueryEscape(query), apiKey,
	))
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Write(body)
}

func omdbDetail(w http.ResponseWriter, r *http.Request) {
	imdbID := r.URL.Query().Get("id")
	if imdbID == "" {
		writeErr(w, http.StatusBadRequest, "id param required")
		return
	}
	apiKey := getEnv("OMDB_API_KEY", "")
	if apiKey == "" {
		writeErr(w, http.StatusServiceUnavailable, "OMDB_API_KEY not configured")
		return
	}
	resp, err := http.Get(fmt.Sprintf(
		"https://www.omdbapi.com/?i=%s&apikey=%s",
		imdbID, apiKey,
	))
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Write(body)
}

// ── Movie handlers ────────────────────────────────────────────────────────────

func scanMovie(row interface{ Scan(...any) error }) (Movie, error) {
	var m Movie
	var myRating sql.NullInt64
	var watchedOn sql.NullString
	err := row.Scan(
		&m.ID, &m.ImdbID, &m.Title, &m.Year, &m.Genre, &m.Director,
		&m.PosterURL, &m.ImdbRating, &myRating, &m.Review, &m.Vibes,
		&m.Watched, &watchedOn, &m.AddedOn,
	)
	if myRating.Valid {
		v := int(myRating.Int64)
		m.MyRating = &v
	}
	if watchedOn.Valid {
		m.WatchedOn = watchedOn.String
	}
	return m, err
}

func moviesHandler(db *sql.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {

		if r.Method == http.MethodGet {
			watched := r.URL.Query().Get("watched")
			genre := r.URL.Query().Get("genre")
			search := r.URL.Query().Get("search")

			query := `SELECT id, imdb_id, title, year, genre, director,
				poster_url, imdb_rating, my_rating, review, vibes,
				watched, watched_on::text, added_on::text
				FROM movies WHERE 1=1`
			var args []any
			i := 1

			if watched == "true" {
				query += fmt.Sprintf(" AND watched=$%d", i); args = append(args, true); i++
			} else if watched == "false" {
				query += fmt.Sprintf(" AND watched=$%d", i); args = append(args, false); i++
			}
			if genre != "" {
				query += fmt.Sprintf(" AND genre ILIKE $%d", i); args = append(args, "%"+genre+"%"); i++
			}
			if search != "" {
				query += fmt.Sprintf(" AND title ILIKE $%d", i); args = append(args, "%"+search+"%"); i++
			}
			query += " ORDER BY added_on DESC"

			rows, err := db.Query(query, args...)
			if err != nil {
				writeErr(w, http.StatusInternalServerError, err.Error()); return
			}
			defer rows.Close()

			movies := []Movie{}
			for rows.Next() {
				m, err := scanMovie(rows)
				if err != nil {
					writeErr(w, http.StatusInternalServerError, err.Error()); return
				}
				movies = append(movies, m)
			}
			writeJSON(w, http.StatusOK, movies)
			return
		}

		if r.Method == http.MethodPost {
			var body Movie
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				writeErr(w, http.StatusBadRequest, "invalid JSON"); return
			}
			if strings.TrimSpace(body.Title) == "" {
				writeErr(w, http.StatusBadRequest, "title required"); return
			}
			var watchedOn *string
			if body.WatchedOn != "" {
				watchedOn = &body.WatchedOn
			}
			var m Movie
			var myRating sql.NullInt64
			var watchedOnOut sql.NullString
			err := db.QueryRow(`
				INSERT INTO movies
					(imdb_id,title,year,genre,director,poster_url,
					 imdb_rating,my_rating,review,vibes,watched,watched_on)
				VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
				RETURNING id,imdb_id,title,year,genre,director,
					poster_url,imdb_rating,my_rating,review,vibes,
					watched,watched_on::text,added_on::text`,
				body.ImdbID, body.Title, body.Year, body.Genre, body.Director,
				body.PosterURL, body.ImdbRating, body.MyRating, body.Review,
				body.Vibes, body.Watched, watchedOn,
			).Scan(
				&m.ID, &m.ImdbID, &m.Title, &m.Year, &m.Genre, &m.Director,
				&m.PosterURL, &m.ImdbRating, &myRating, &m.Review, &m.Vibes,
				&m.Watched, &watchedOnOut, &m.AddedOn,
			)
			if err != nil {
				writeErr(w, http.StatusInternalServerError, err.Error()); return
			}
			if myRating.Valid { v := int(myRating.Int64); m.MyRating = &v }
			if watchedOnOut.Valid { m.WatchedOn = watchedOnOut.String }
			writeJSON(w, http.StatusCreated, m)
			return
		}

		writeErr(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func movieByIDHandler(db *sql.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		idStr := strings.TrimPrefix(r.URL.Path, "/movies/")
		id, err := strconv.Atoi(idStr)
		if err != nil {
			writeErr(w, http.StatusBadRequest, "invalid id"); return
		}

		if r.Method == http.MethodPatch {
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				writeErr(w, http.StatusBadRequest, "invalid JSON"); return
			}
			setClauses := []string{}
			args := []any{}
			i := 1
			for _, f := range []string{"my_rating", "review", "vibes", "watched", "watched_on"} {
				if v, ok := body[f]; ok {
					setClauses = append(setClauses, fmt.Sprintf("%s=$%d", f, i))
					args = append(args, v); i++
				}
			}
			if len(setClauses) == 0 {
				writeErr(w, http.StatusBadRequest, "no fields to update"); return
			}
			args = append(args, id)
			row := db.QueryRow(fmt.Sprintf(
				`UPDATE movies SET %s WHERE id=$%d
				 RETURNING id,imdb_id,title,year,genre,director,
				   poster_url,imdb_rating,my_rating,review,vibes,
				   watched,watched_on::text,added_on::text`,
				strings.Join(setClauses, ","), i,
			), args...)
			m, err := scanMovie(row)
			if err != nil {
				writeErr(w, http.StatusInternalServerError, err.Error()); return
			}
			writeJSON(w, http.StatusOK, m)
			return
		}

		if r.Method == http.MethodDelete {
			_, err := db.Exec(`DELETE FROM movies WHERE id=$1`, id)
			if err != nil {
				writeErr(w, http.StatusInternalServerError, err.Error()); return
			}
			writeJSON(w, http.StatusOK, map[string]string{"deleted": idStr})
			return
		}

		writeErr(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	db := connectWithRetry()
	defer db.Close()
	initSchema(db)

	port := getEnv("SERVER_PORT", "8080")
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/movies", moviesHandler(db))
	mux.HandleFunc("/movies/", movieByIDHandler(db))
	mux.HandleFunc("/omdb/search", omdbSearch)
	mux.HandleFunc("/omdb/detail", omdbDetail)

	log.Printf("Connector listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

"use client";

import { FormEvent, useState } from "react";

export default function Home() {
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [platform, setPlatform] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [analyzedUrl, setAnalyzedUrl] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setMessage("");
    setPlatform("");
    setAnalyzedUrl("");

    if (!url.trim()) {
      setMessage("Please enter a social media URL.");
      return;
    }

    try {
      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: url.trim(),
        }),
      });

      const data = await response.json();

      if (data.success) {
  setPlatform(data.platform);
  setIdentifier(data.identifier);
  setAnalyzedUrl(data.url);
      } else {
        setMessage(data.message);
      }
    } catch {
      setMessage("Unable to connect to the backend.");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        <h1 className="text-4xl font-bold text-center">
          Social Media Engagement Analyzer
        </h1>

        <p className="text-center mt-3 text-gray-600">
          Enter your social media profile URL to begin analysis.
        </p>

        <form onSubmit={handleSubmit} className="mt-8">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.instagram.com/username/"
            className="w-full border rounded-lg p-4"
          />

          <button
            type="submit"
            className="w-full mt-4 rounded-lg p-4 font-semibold border"
          >
            Analyze
          </button>
        </form>

        {platform && (
          <div className="mt-6 border rounded-lg p-5">
            <p className="font-semibold">✓ URL Valid</p>

            <p className="mt-4 text-gray-600">Platform</p>
            <p className="font-semibold text-lg">{platform}</p>

            <p className="mt-4 text-gray-600">Profile Identifier</p>
            <p className="font-semibold text-lg">{identifier}</p>

            <p className="mt-4 text-gray-600">URL</p>
            <p className="break-all">{analyzedUrl}</p>
          </div>
        )}

        {message && (
          <p className="text-center mt-5 font-medium">
            {message}
          </p>
        )}

        <p className="text-center mt-8 text-sm text-gray-500">
          Instagram • YouTube • X (Twitter)
        </p>
      </div>
    </main>
  );
}
import React, { useState } from 'react';

/**
 * ProductCardCarousel — Displays multiple analyzed products in an interactive carousel
 * with slide controls, thumbnail pills, individual product capabilities, and unified taxonomy guidance.
 */
export default function ProductCardCarousel({
  mentalModel,
  uploadedProducts = [],
  patentIds = [],
  onTriggerBuild,
  onSendMessage,
  onSetInput
}) {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Collect all products: either from mentalModel.products, or uploadedProducts prop, or fallback to single
  let productList = [];
  if (mentalModel?.products && Array.isArray(mentalModel.products) && mentalModel.products.length > 0) {
    productList = mentalModel.products;
  } else if (uploadedProducts && uploadedProducts.length > 0) {
    productList = uploadedProducts;
  } else if (mentalModel?.product_name) {
    productList = [{
      product_id: 'prod_default',
      product_name: mentalModel.product_name,
      category: mentalModel.domain,
      features: mentalModel.key_features || mentalModel.key_capabilities || [],
      source_filename: mentalModel.product_name
    }];
  }

  const total = productList.length;
  const safeIndex = Math.min(Math.max(0, currentIndex), Math.max(0, total - 1));
  const currentProduct = productList[safeIndex] || {};

  const handlePrev = () => {
    setCurrentIndex(prev => Math.max(0, prev - 1));
  };

  const handleNext = () => {
    setCurrentIndex(prev => Math.min(total - 1, prev + 1));
  };

  const features = (currentProduct.features && currentProduct.features.length > 0)
    ? currentProduct.features
    : (mentalModel?.key_features || mentalModel?.key_capabilities || []);

  const truncate = (str, max = 24) => {
    if (!str) return '';
    return str.length > max ? str.slice(0, max) + '...' : str;
  };

  return (
    <div style={{
      marginTop: 14,
      padding: 16,
      background: '#090d16',
      borderRadius: 12,
      border: '1px solid #059669',
      boxShadow: '0 4px 20px rgba(5, 150, 105, 0.2)',
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }}>
      {/* Carousel Navigation Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1e293b', paddingBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>📦</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#34d399', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>Product Specifications Analysis</span>
              {total > 1 && (
                <span style={{ fontSize: 11, background: '#064e3b', color: '#6ee7b7', border: '1px solid #059669', padding: '1px 7px', borderRadius: 10, fontWeight: 600 }}>
                  {safeIndex + 1} of {total} Products
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              {total > 1 ? `Browsing specifications for ${total} linked products` : 'Extracted technical specification & capabilities'}
            </div>
          </div>
        </div>

        {/* Carousel controls if more than 1 product */}
        {total > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              onClick={handlePrev}
              disabled={safeIndex === 0}
              style={{
                background: safeIndex === 0 ? '#1e293b' : '#047857',
                color: safeIndex === 0 ? '#475569' : '#ffffff',
                border: '1px solid ' + (safeIndex === 0 ? '#334155' : '#059669'),
                borderRadius: 6,
                padding: '3px 8px',
                fontSize: 12,
                fontWeight: 700,
                cursor: safeIndex === 0 ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease'
              }}
              title="Previous Product"
            >
              ◀ Prev
            </button>

            <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, padding: '0 4px' }}>
              {safeIndex + 1} / {total}
            </span>

            <button
              type="button"
              onClick={handleNext}
              disabled={safeIndex === total - 1}
              style={{
                background: safeIndex === total - 1 ? '#1e293b' : '#047857',
                color: safeIndex === total - 1 ? '#475569' : '#ffffff',
                border: '1px solid ' + (safeIndex === total - 1 ? '#334155' : '#059669'),
                borderRadius: 6,
                padding: '3px 8px',
                fontSize: 12,
                fontWeight: 700,
                cursor: safeIndex === total - 1 ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease'
              }}
              title="Next Product"
            >
              Next ▶
            </button>
          </div>
        )}
      </div>

      {/* Quick Jump Tabs / Carousel Slide Pills */}
      {total > 1 && (
        <div style={{
          display: 'flex',
          gap: 6,
          overflowX: 'auto',
          paddingBottom: 4,
          scrollbarWidth: 'thin'
        }}>
          {productList.map((p, idx) => {
            const isSelected = idx === safeIndex;
            return (
              <button
                key={p.product_id || idx}
                type="button"
                onClick={() => setCurrentIndex(idx)}
                style={{
                  background: isSelected ? '#047857' : '#1e293b',
                  color: isSelected ? '#ffffff' : '#94a3b8',
                  border: `1px solid ${isSelected ? '#34d399' : '#334155'}`,
                  borderRadius: 12,
                  padding: '3px 10px',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
              >
                <span>{isSelected ? '●' : '○'}</span>
                <span>{idx + 1}. {truncate(p.product_name || p.source_filename || `Product ${idx + 1}`, 22)}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Active Product Slide Content */}
      <div style={{
        background: '#0c1524',
        border: '1px solid #1e3a5f',
        borderRadius: 10,
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10
      }}>
        {/* Product Title & Category */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.01em' }}>
              {currentProduct.product_name || currentProduct.source_filename || 'Product Specification'}
            </div>
            {currentProduct.source_filename && (
              <div style={{ fontSize: 11, color: '#38bdf8', marginTop: 2, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span>🔗</span>
                <span style={{ wordBreak: 'break-all' }}>{currentProduct.source_filename}</span>
              </div>
            )}
          </div>

          <span style={{
            fontSize: 11,
            background: '#065f46',
            color: '#a7f3d0',
            padding: '2px 8px',
            borderRadius: 8,
            fontWeight: 600,
            whiteSpace: 'nowrap'
          }}>
            {currentProduct.category || mentalModel?.domain || 'Technical Domain'}
          </span>
        </div>

        {/* Key Features & Capabilities of this product */}
        {features && features.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
              Key Technical Capabilities & Parameters:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {features.slice(0, 6).map((feat, i) => (
                <div key={i} style={{ fontSize: 12, color: '#e2e8f0', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <span style={{ color: '#10b981', flexShrink: 0 }}>•</span>
                  <span>{feat}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Excerpt / Table parameters */}
        {currentProduct.full_text_snippet && (
          <div style={{
            padding: '8px 10px',
            background: '#050c18',
            borderRadius: 6,
            border: '1px solid #1e293b',
            fontSize: 11,
            color: '#94a3b8',
            maxHeight: 70,
            overflowY: 'auto',
            lineHeight: 1.4
          }}>
            <span style={{ color: '#38bdf8', fontWeight: 600 }}>Excerpt: </span>
            <span>{currentProduct.full_text_snippet.slice(0, 320)}...</span>
          </div>
        )}
      </div>

      {/* Unified Priority Taxonomy Focus (Guided by all products) */}
      {mentalModel?.focus_areas && mentalModel.focus_areas.length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
            Priority Taxonomy Focus (Synthesized from {total} Product{total > 1 ? 's' : ''}):
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {mentalModel.focus_areas.map((fa, i) => (
              <span key={i} style={{ fontSize: 11, background: '#1e293b', border: '1px solid #047857', color: '#6ee7b7', padding: '2px 8px', borderRadius: 8 }}>
                🎯 {fa}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4, paddingTop: 10, borderTop: '1px solid #1e293b' }}>
        <button
          type="button"
          onClick={() => {
            if (patentIds.length > 0) {
              onTriggerBuild();
            } else {
              onSendMessage("I'm ready to build. Please extract patent categories based on these products.");
            }
          }}
          style={{
            background: '#059669',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6
          }}
        >
          <span>✓ Looks good, build taxonomy</span>
        </button>
        <button
          type="button"
          onClick={() => {
            if (onSetInput) {
              onSetInput("Focus specifically on mechanism of action, avoid manufacturing: ");
            }
          }}
          style={{
            background: '#334155',
            color: '#cbd5e1',
            border: 'none',
            borderRadius: 6,
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer'
          }}
        >
          <span>✏️ Adjust Focus / Instructions</span>
        </button>
      </div>
    </div>
  );
}
